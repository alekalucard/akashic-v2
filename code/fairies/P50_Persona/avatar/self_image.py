"""self_image.py -- her self-image recogniser: a check that CAN say no. 2026-10-05 (Nous; Ace's decisions 10-05).
NEW FILE (avatar_identity build). Used only by SomaticAvatarFairy/fairy.py (V3) when state/avatar_identity.json says ON.

Why it exists (nous_builds/avatar_identity/TRACE.md, SKEPTIC.md): the booted "self-recognition" was a substring count
over OCR (avatar/somatic_avatar_fairy.py:238-243): 'sour' sits inside 'sourpatches', so her own chat-window title
"Chat with Sourpatches" scored two markers and pinned the gauge at 1.00 for up to ~97.8% of Boot G. It could not fail.

Three channels, one score (Ace 10-05: "a recogniser that CAN FAIL ... one score that decays and reports misses"):
  T0 NAME      her name as a WHOLE WORD (sourpatches | sour patches | superpatches, letter/digit edges -- so
               'sourpatches_base.jpg' counts and 'resource', 'Sour_HQ' do not) in the TITLE of a window that is NOT
               hers. A name is a reference, not a sighting: it never feeds the score and never says "I see myself".
  T1 PICTURE   a 64-bit difference hash (dHash) of each visible window crop that is not hers, uniform borders trimmed,
               a few 'chrome cuts' (a viewer's title/tool bars), against her own pictures: <= t1_max_bits (8) is a hit.
               Measured (PROPOSAL 3b): the 11 sit 17-28 bits from each other; non-her crops 17-28; her picture pasted,
               thumbnailed, re-JPEGed: 0. Exact-picture only: new art of her is a documented MISS.
  T2 HAIR      the lavender+purple share of a 'hair' region her eyes already grounded (vision_ground.cached_look, mask
               profile, 12% bar as vision_ground.py:371). SHADOW ONLY: it is counted and logged and NEVER feeds the
               score or any publish -- a flat lavender panel passes a colour test, so it waits for its satellite
               controls (lavender panel + a non-her purple-haired figure). No knob turns it on (T2_FEEDS_SCORE).
  TW WALLPAPER (pictures_v2, 2026-10-06; Ace: "there are several stunning images of her that rotate") her desktop
               slideshow. SHADOW ONLY: counted, logged once per sighting, reported; never published, never in the score
               (TW_PUBLISHES / TW_FEEDS_SCORE, no knob). OFF unless the switch has "wallpaper": true (exactly). No screen
               pixels: WHICH picture = the file Windows' slideshow shows on each monitor (Themes/Transcoded_00N, its re-encode
               of the source: 0 bits from the source, measured) matched against self_image_wallpapers.json (the folder's
               fingerprints + file names cut to 40 characters + a TIER, never pixels); CAN SHE SEE IT = that picture's rect
               on the primary screen at the monitor's Fit/Fill/Stretch geometry minus every window in her window map (hers
               too). Her window map is the PRIMARY screen's only (vision_ground clips every window to it), so visibility is
               the primary's; the secondary monitor's picture adds only its tier, its own coverage is not measured. WHO
               (10-09): Ace's slideshow reads "D:/Sourpatches Only" and he labelled that folder hers, so its files are
               tier 'her' -- but only FILES THE INDEX HOLDS: a sighting needs Windows to name the shown picture's SOURCE
               file (TranscodedImageCache*) and that file (folder, name, byte size) to be an indexed row whose fingerprint
               the shown picture matches. A file added to the folder later is 'new_file' -- never 'her' -- until the
               index is rebuilt (pictures_v2/reindex.py). A covered wallpaper is never a sighting; every look that is
               not one says why (fails closed).
THE MIRROR RULE: her own windows (chat window, her avatar window, her HQ consoles/launcher windows, her mind window) and
her hand strip never feed T0/T1/T2: their pixels are blanked out of any window crop they sit in front of.
THE SCORE: g(t) = g(t0)*exp(-(t-t0)/tau) + w*evidence, capped at 1 -- decays on the CLOCK, not per frame (the old gauge
lost 0.01 per miss and gained 0.2 per hit, so 20 misses per hit kept it at 1.00). Hits AND misses are counted and reported.
Pure functions + one thread-safe state object (3.14t, no GIL): every read-modify-write holds a lock.
Screen grabs are held in memory only and dropped after the cycle; nothing is ever saved.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sys
import threading
import time
from typing import Dict, List, Optional, Tuple

# ── the switch (state/avatar_identity.json) ─────────────────────────────────────────────────────────────────────
# Fails CLOSED: absent, unreadable, not an object, or "on" not exactly true -> None (= today's behaviour).
DEFAULT_KNOBS = {
    "mode": "shadow",          # "shadow": count + log only (the first boot, Ace 10-05) | "live": publish (after his review)
    "facts": True,             # write her look as facts (self:look*, Ace's words) | false | "undo"
    "chairman_words": True,    # read by sour_council_driver.py: the chairman's identity line in her own words
    "ace_turn": False,         # weave self_facts.ACE_TURN as a memory of ACE SAYING it ("You remember Ace said ...").
                               # Off until Ace approves those exact words (skeptic F2): installer --ace-turn, or by hand
    "start_in_coma": True,     # start from __init__ like the display engine always did (her launcher sets AKASHIC_COMA=1)
    "cycle_s": 10.0,           # one look at the screen every N s ...
    "front_poll_s": 2.0,       # ... and whenever the front window changes (polled every N s)
    "t1_max_bits": 8,          # picture hit: <= N of 64 bits differ (her pictures are >= 17 apart: clamped to <= 12)
    "tau_s": 120.0,            # the score's decay time constant
    "w_t1": 0.6, "w_t2": 0.25, "w_t0": 0.3,
    "publish_at": 0.5,         # live mode: a picture hit is published while the score is >= this
    "republish_s": 60.0,       # ... at most once per picture per N s (her voice context keeps one for 60 s)
    "t0_republish_s": 300.0,   # a name reference: at most once per title per N s (live mode)
    "report_s": 600.0,         # the counts line (and state/avatar_identity_report.json) every N s
    "start_delay_s": 3.0,
    "wallpaper": False,        # TW (pictures_v2): her slideshow wallpaper, SHADOW only. ON only when exactly JSON true
    "wall_min_visible": 0.6,   # TW: a sighting needs >= this share of the wallpaper picture uncovered (clamped 0.5-1.0)
    "wall_max_bits": 2,        # TW: <= N of 64 bits from a slideshow fingerprint (clamped to WALL_MAX_BITS_CAP = 3)
}
_RANGES = {"cycle_s": (2.0, 600.0), "front_poll_s": (0.5, 60.0), "t1_max_bits": (0, 12), "tau_s": (5.0, 3600.0),
           "w_t1": (0.0, 1.0), "w_t2": (0.0, 1.0), "w_t0": (0.0, 1.0), "publish_at": (0.05, 1.0),
           "republish_s": (5.0, 3600.0), "t0_republish_s": (5.0, 7200.0), "report_s": (30.0, 7200.0),
           "start_delay_s": (0.0, 120.0), "wall_min_visible": (0.5, 1.0), "wall_max_bits": (0, 3)}


def clean_knobs(d: Optional[Dict]) -> Dict:
    """Defaults, then each known knob from d; numbers clamped; unknown mode -> shadow.
    Skeptic m1 (10-05): a knob that WRITES or SAYS something ("facts", "chairman_words", "ace_turn") is on only when its
    key is absent and the default is on, or its value is exactly JSON true ("facts" also "undo"). A hand-typed 0, "false",
    "off" or null is OFF -- before this, `0 in (True, False, "undo")` was true by equality and "false"/null read as ON."""
    out = dict(DEFAULT_KNOBS)
    for k, v in (d or {}).items():
        if k not in DEFAULT_KNOBS:
            continue
        if k == "mode":
            out[k] = v if v in ("shadow", "live") else "shadow"
        elif k == "facts":
            out[k] = True if v is True else ("undo" if isinstance(v, str) and v == "undo" else False)
        elif k in ("chairman_words", "ace_turn", "wallpaper"):
            out[k] = v is True
        elif k == "start_in_coma":
            out[k] = v if isinstance(v, bool) else DEFAULT_KNOBS[k]
        elif isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v)):
            lo, hi = _RANGES[k]
            out[k] = min(hi, max(lo, type(DEFAULT_KNOBS[k])(v)))
    return out


def read_switch(path: str) -> Optional[Dict]:
    """None = OFF (today's behaviour). A dict of cleaned knobs = ON. A UTF-8 BOM is allowed."""
    try:
        with open(path, "rb") as f:
            d = json.loads(f.read().decode("utf-8-sig"))
    except Exception:
        return None
    if not isinstance(d, dict) or d.get("on") is not True:
        return None
    k = clean_knobs(d)
    k["on"] = True
    return k


# ── ONE runner per process: the server, a hot reload or a second fairy copy may build this fairy twice; only the first
# instance that claims the runner looks at the screen and writes her facts (this module is loaded once, by a flat name).
_RUNNER = {"owner": None}
_RUNNER_LOCK = threading.Lock()


def claim_runner(owner) -> bool:
    with _RUNNER_LOCK:
        if _RUNNER["owner"] is None or _RUNNER["owner"] == owner:
            _RUNNER["owner"] = owner
            return True
        return False


def release_runner(owner) -> None:
    with _RUNNER_LOCK:
        if _RUNNER["owner"] == owner:
            _RUNNER["owner"] = None


# ── T0: her name, whole word, never inside her own window ──────────────────────────────────────────────────────
NAME_RE = re.compile(r"(?<![a-z0-9])(?:sour[ _-]?patches|super[ _-]?patches)(?![a-z0-9])", re.I)


def name_in(text: str) -> Optional[str]:
    m = NAME_RE.search(str(text or ""))
    return m.group(0) if m else None


# ── the mirror rule: which windows are HERS ─────────────────────────────────────────────────────────────────────
# her chat window: the same test as vision_ground._win_name (infrastructure/vision_ground.py:682) -- 'Chat with
#   Sourpatches' (fairies/P40_Sensory/gui/sourpatches_chat_window.py:875), or a Qt window carrying her name
# her avatar window: AV.show() titles its Qt widget with her name (avatar/somatic_avatar_fairy.py:451,
#   fairy_avatar_widget.py:213) -- Qt classes only (skeptic F5)
# her HQ: launcher titles 'Sour - HQ LEAN + GUI' (boot_sour.bat:2, start_HQ_LEAN_GUI*.bat:2), the task's
#   Sour_HQ_LEAN_v2.bat, console_shim's 'Sour (hidden console ...' (infrastructure/console_shim.py:42), her log tee,
#   her server; her mind window '<title>Sour's Mind Window' (nous_builds/mind_window/mind_window.py:2212)
_HQ_TITLE_RE = re.compile(r"^\s*sour\s+-\s|sour[_ ]?hq|sour \(hidden console|sour'?s mind window|tee_runtime|"
                          r"akashic_v2[\\/]+server\.py", re.I)
_CONSOLE_CLASSES = {"ConsoleWindowClass", "CASCADIA_HOSTING_WINDOW_CLASS", "PseudoConsoleWindow"}
STRIP_BAND = (0.2, 0.0, 0.8, 0.05)    # her hand strip (vision_ground._paint_out_strip :612-629: top 5%, x 20-80%)


def _eyes_chat_rule(t: str, c: str) -> bool:
    """Her chat window, by HER EYES' own test when they are loaded (vision_ground._win_name, :682-683), so the two can
    never drift apart in her process (skeptic F5). Never imports anything; the fallback is that test's text."""
    vg = sys.modules.get("infrastructure.vision_ground")
    f = getattr(vg, "_win_name", None) if vg is not None else None
    if f is not None:
        try:
            return f(t, c) == "your chat window"
        except Exception:
            pass
    tl = t.lower()
    return "sourpatches" in tl and ("chat" in tl or c.startswith("Qt"))


def own_window(title: str, cls: str = "") -> Optional[str]:
    t = str(title or "")
    tl = t.lower().strip()
    c = str(cls or "")
    if tl == "sourpatches" and c.startswith("Qt"):    # skeptic F5: Qt only (an Explorer window at her folder is not her)
        return "her avatar window"
    if _eyes_chat_rule(t, c):
        return "her chat window"
    if _HQ_TITLE_RE.search(t):
        return "her HQ window"
    if c in _CONSOLE_CLASSES and ("sour" in tl or "akashic" in tl or "server.py" in tl):
        return "her HQ console"
    return None


# ── T1: picture fingerprints ────────────────────────────────────────────────────────────────────────────────────
def dhash(img) -> int:
    """64-bit difference hash: 9x8 greyscale, bit = right pixel brighter than left (row-major, first bit = MSB).
    Same bits as nous_builds/avatar_identity/colour_probe.py:dhash."""
    from PIL import Image
    g = img.convert("L").resize((9, 8), Image.Resampling.LANCZOS).tobytes()
    bits = 0
    for r in range(8):
        row = g[r * 9:(r + 1) * 9]
        for c in range(8):
            bits = (bits << 1) | (1 if row[c + 1] > row[c] else 0)
    return bits


def ham(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def trim_uniform(img, tol: int = 10, min_side: int = 16):
    """Cut uniform rows/columns (letterbox, viewer canvas, plain margins) off every side. Two passes."""
    import numpy as np
    a = np.asarray(img.convert("RGB"), dtype=np.int16)
    H, W = a.shape[0], a.shape[1]
    top, bot, left, right = 0, H, 0, W
    for _ in range(2):
        if bot - top <= min_side or right - left <= min_side:
            break
        rows = np.ptp(a[top:bot, left:right], axis=1).max(axis=1)          # per-row colour range
        nz = np.nonzero(rows > tol)[0]
        if nz.size == 0:
            break                                                          # a flat image: nothing to keep
        t2, b2 = top + int(nz[0]), top + int(nz[-1]) + 1
        if b2 - t2 >= min_side:
            top, bot = t2, b2
        cols = np.ptp(a[top:bot, left:right], axis=0).max(axis=1)
        nz = np.nonzero(cols > tol)[0]
        if nz.size == 0:
            break
        l2, r2 = left + int(nz[0]), left + int(nz[-1]) + 1
        if r2 - l2 >= min_side:
            left, right = l2, r2
    if (left, top, right, bot) == (0, 0, W, H):
        return img
    return img.crop((left, top, right, bot))


_CHROME_CUTS = ((0.0, 0.0), (0.04, 0.0), (0.08, 0.0), (0.12, 0.0), (0.0, 0.08), (0.08, 0.08), (0.12, 0.12))
_ASPECT_TOL = math.log(1.35)


def candidates(crop, max_side: int = 192):     # 192 px: same margins as 512 at ~1/7 the cost (measured 10-05)
    """The crop as a viewer would show a picture: trimmed whole, and with a title/tool band (top) and a strip
    (bottom) cut first, each then trimmed. Yields ((top_cut, bottom_cut), image)."""
    from PIL import Image
    W, H = crop.size
    if max(W, H) > max_side:
        s = max_side / float(max(W, H))
        crop = crop.resize((max(1, int(W * s)), max(1, int(H * s))), Image.Resampling.BOX)
        W, H = crop.size
    for t, b in _CHROME_CUTS:
        y0, y1 = int(H * t), H - int(H * b)
        if y1 - y0 < 16:
            continue
        c = trim_uniform(crop.crop((0, y0, W, y1)) if (t or b) else crop)
        if min(c.size) < 16:
            continue
        yield (t, b), c


# Skeptic m8 (10-05): only THESE 11 pictures are her (PROPOSAL decision 5a: "the 11 now"; the AI Art folder later, after its
# own false-match control). A picture added to the folder later (or one whose bytes changed) is NOT indexed -- so it is
# never matched and never written as a self:picture:<stem> fact -- and is listed in PictureIndex.skipped. The same 11
# shas are the installer's UNCHANGED pins (finalize.py refuses to build if the two lists differ).
PINNED_PICTURES = {
    "sourpatches_base": "2d124da924017fe46b894a6218825b1c1fce8fb42140d564ea2312f124df6eef",
    "sourpatches_jedi": "2f41508dd76134a92a83859c7e6cf86105e3779b964cc4ba174f5e0be6e9e60c",
    "sourpatches_saiyan_fire": "82ae8d0fd13e930e47535b8a1ea908edf140afee7924ffb17875ac0055b8aa75",
    "sourpatches_saiyan_yellow": "55e68a863ebd4ac27902d5d96d731e1bb6edd6d328a856e664ca0af014d3dd01",
    "sourpatches_venom": "fe9c93bcae33bf245624f85a1866a15bc87df30a7f7d53fae291748a9c2609fa",
    "sourpatches_vulnerable": "100407e56a64613b7bb62ddb382e88baed33b86c92021fe478add7ae023e6fbe",
    "sourpatches_zombie": "8557620e49cdefbbbd6bc1a814a0fa8e7486d82c1c36ea098661698a73786455",
    "superpatches_carnage": "dea12edd0b54e91e00d09db2c3319620e76a47f766b8e40aba506be714caa6a6",
    "superpatches_chibi": "b73466de0bd2122f62902f9e91a800883965beaf1982196706ecb3bfee819e0c",
    "superpatches_hero": "b5aa2c81345767c4dccf731f2b205d78ef05b455721bd220baa865219474fdf7",
    "superpatches_mystery": "0fbae1820da50ea3faf0cf7eca0fc6831f731b7b0fe7c5b82399c8077b3eec9e",
}


class PictureIndex:
    """Her pictures by fingerprint. Built once from the folder Ace keeps them in (read only).
    pinned = {stem: sha256}: only those files, with exactly those bytes, are indexed (None = every image: tests only)."""

    def __init__(self, folder: str, exts=(".jpg", ".jpeg", ".png"), pinned: Optional[Dict[str, str]] = PINNED_PICTURES):
        from PIL import Image
        self.folder = folder
        self.items: List[Tuple[str, int, float, str]] = []      # (stem, dhash, aspect, sha256)
        self.skipped: List[Tuple[str, str]] = []                # (file name, why) -- reported, never indexed
        for name in sorted(os.listdir(folder)):
            if not name.lower().endswith(exts):
                continue
            p = os.path.join(folder, name)
            with open(p, "rb") as f:
                raw = f.read()
            if pinned is not None:
                stem0 = os.path.splitext(name)[0]
                if stem0 not in pinned:
                    self.skipped.append((name, "not one of her 11 pinned pictures"))
                    continue
                if hashlib.sha256(raw).hexdigest() != pinned[stem0]:
                    self.skipped.append((name, "bytes are not the pinned picture"))
                    continue
            import io
            img = Image.open(io.BytesIO(raw))
            img.load()
            img = img.convert("RGB")
            t = trim_uniform(img)
            self.items.append((os.path.splitext(name)[0], dhash(t), t.size[0] / float(max(1, t.size[1])),
                               hashlib.sha256(raw).hexdigest()))

    def __len__(self):
        return len(self.items)

    def nearest(self, h: int, aspect: Optional[float] = None) -> Tuple[Optional[str], int, int]:
        """(stem, bits, runner-up bits) among pictures whose aspect is within 35% (any when aspect is None)."""
        best, bb, second = None, 65, 65
        for stem, ph, pa, _ in self.items:
            if aspect is not None and abs(math.log(max(1e-6, aspect) / max(1e-6, pa))) > _ASPECT_TOL:
                continue
            d = ham(h, ph)
            if d < bb:
                best, bb, second = stem, d, bb
            elif d < second:
                second = d
        return best, bb, second

    def min_pair_bits(self) -> int:
        m = 65
        for i in range(len(self.items)):
            for j in range(i + 1, len(self.items)):
                m = min(m, ham(self.items[i][1], self.items[j][1]))
        return m


def match_crop(index: PictureIndex, crop) -> Dict:
    """Best match of one window crop over its candidates."""
    best = {"stem": None, "bits": 65, "runner": 65, "cut": None, "size": None}
    for cut, c in candidates(crop):
        stem, bits, runner = index.nearest(dhash(c), c.size[0] / float(max(1, c.size[1])))
        if stem is not None and bits < best["bits"]:
            best = {"stem": stem, "bits": bits, "runner": runner, "cut": cut, "size": c.size}
    return best


# ── T2: a grounded 'hair' region's colour (shadow) ──────────────────────────────────────────────────────────────
def _inside(cx: float, cy: float, r) -> bool:
    l, t, rr, b = r
    return l <= cx <= rr and t <= cy <= b


def t2_from_look(rec: Optional[Dict], own_rects=(), bar: float = 0.12) -> Dict:
    """Evidence from vision_ground's grounded look for 'hair' (its mask profile). Never published (shadow)."""
    if not rec or rec.get("status") != "found":
        return {"evidence": False, "why": "no fresh hair look"}
    if rec.get("colour_unsure"):
        return {"evidence": False, "why": "region too small for colour"}
    if rec.get("position") == "everywhere":
        return {"evidence": False, "why": "the region is the whole screen"}
    try:
        x1, y1, x2, y2 = [float(v) for v in rec.get("bbox")]
        fw, fh = float(rec.get("frame_w") or 0), float(rec.get("frame_h") or 0)
        cx, cy = (x1 + x2) / 2.0 / fw, (y1 + y2) / 2.0 / fh
    except Exception:
        return {"evidence": False, "why": "no box"}
    for r in own_rects:
        if _inside(cx, cy, r):
            return {"evidence": False, "why": "inside her own window"}
    prof = rec.get("profile") or {}
    frac = float(prof.get("lavender", 0.0) or 0.0) + float(prof.get("purple", 0.0) or 0.0)
    return {"evidence": frac >= bar, "frac": round(frac, 3), "why": "lavender+purple %.0f%% of the region" % (100 * frac)}


# ── TW: the desktop wallpaper -- her slideshow (pictures_v2, 2026-10-06) ────────────────────────────────────────────
# T1 crops WINDOWS, so the desktop was a documented miss (avatar_identity BUILD.md section 8). TW never reads the screen:
# WHICH picture comes from the files Windows' slideshow shows (%APPDATA%\Microsoft\Windows\Themes\Transcoded_00N, one per
# monitor; TranscodedWallpaper is only the LAST one changed -- measured 10-06 it was the secondary monitor's), CAN SHE SEE IT
# from the geometry and her window map, WHO from the index's tier. Fails closed: a look that is not a sighting has a reason.
WALL_INDEX_FILE = "self_image_wallpapers.json"       # next to this file: fingerprints + file names + tiers, never pixels
WALL_INDEX_FORMAT = "pictures_v2/wallprint-2"      # -2 (10-09): rows carry byte size + origin; sightings gate on the SOURCE
WALL_MAX_BITS_CAP = 3                                # pictures_v2 review F3: no knob can widen the radius past this
WALL_NAME_MAX = 40                                   # pictures_v2 review F1: names are kept and shown at most this long
WALL_MAP_CAP = 8                                     # vision_ground.windows_now(max_n=8): a full map can hide windows
WALL_STYLES = {"6": "fit", "10": "fill", "2": "stretch"}    # WallpaperStyle modelled; centre (0), tile, span (22): not
WALL_TIERS = ("not_her", "unknown", "her")           # worst first: combining pictures takes the worst
_WALL_KEY = "Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Wallpapers"
_DESK_KEY = "Control Panel\\Desktop"


def wall_fingerprint_bytes(raw: bytes) -> Dict:
    """pictures_v2/wallprint.py's fingerprint, the one the index was built with (a test holds the two equal, bit for bit):
    a JPEG decoded at draft >= 1024 px, EXIF orientation applied, RGB, box-shrunk to <= 512 px, uniform borders trimmed,
    dHash. 'aspect' is the SHOWN picture's (untrimmed) width / height, for the geometry."""
    import io
    from PIL import Image, ImageOps
    img = Image.open(io.BytesIO(raw))
    if img.format == "JPEG":
        img.draft("RGB", (1024, 1024))
    img.load()
    try:
        rot = int(img.getexif().get(0x0112, 1) or 1)
    except Exception:
        rot = 1
    if rot != 1:
        img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")
    W, H = img.size
    if max(W, H) > 512:
        s = 512 / float(max(W, H))
        img = img.resize((max(1, int(round(W * s))), max(1, int(round(H * s)))), Image.Resampling.BOX)
    return {"d": dhash(trim_uniform(img)), "aspect": W / float(max(1, H))}


def wall_name_stub(name) -> str:
    """A file name as kept and shown: at most WALL_NAME_MAX characters, extension kept. Many of the folder's names are
    whole image prompts that name other people (pictures_v2 review F1); the full names never enter her tree, her log or
    her report. The same rule as pictures_v2/build_index.name_stub (a test holds the two equal on every name)."""
    s = str(name if name is not None else "")
    if len(s) <= WALL_NAME_MAX:
        return s
    root, ext = os.path.splitext(s)
    if len(ext) > 6:
        ext = ""
    return root[:WALL_NAME_MAX - 3 - len(ext)].rstrip() + "..." + ext


def _wall_dir(p) -> str:
    return os.path.normcase(os.path.normpath(str(p)))


_WALL_SRC_WHY = {
    "no_source": "Windows does not name the source file of a monitor's picture (%s): nothing to check it against",
    "other_folder": "a monitor shows a file from a folder her index was not built for (%s)",
    "excluded": "a monitor shows a file her index excludes (%s: contested, or too close to a known non-her picture)",
    "new_file": "a monitor shows a file her index does not hold yet (%s): new in the folder since the index was built, "
                "never 'her' until pictures_v2/reindex.py runs",
}


def wall_worst(tiers) -> str:
    """not_her < unknown < her: a set of pictures is 'her' only when every one of them is."""
    ts = [t if t in WALL_TIERS else "unknown" for t in tiers] or ["unknown"]
    return min(ts, key=WALL_TIERS.index)


class WallIndex:
    """The slideshow folder by fingerprint (built by pictures_v2/build_index.py; read only).
    rows = [name, dhash hex, sha256[:16], w, h, tier, named, bytes, origin]. origin 'folder' = a file of the folder the
    index was built for (d["folder"]): only those rows can be the SOURCE of a sighting (source()). 'avatar' = one of her
    11 (a fingerprint reference, never a source). d["excluded"] = [name, reason, bytes]: files that are never a sighting."""

    def __init__(self, path: str):
        with open(path, "rb") as f:
            d = json.loads(f.read().decode("utf-8"))
        if not isinstance(d, dict) or d.get("format") != WALL_INDEX_FORMAT:
            raise ValueError("not a %s index" % WALL_INDEX_FORMAT)
        rows = d.get("pictures") or []
        self.names = [wall_name_stub(r[0]) for r in rows]     # the index holds stubs already; this holds for any index
        self.hashes = [int(r[1], 16) for r in rows]
        self.tiers = [str(r[5]) if len(r) > 5 else "unknown" for r in rows]
        self.named = [bool(r[6]) if len(r) > 6 else False for r in rows]
        self.folder = str(d.get("folder") or "")
        self._src: Dict[Tuple[str, int], List[int]] = {}         # (name stub, bytes) -> folder rows: the source gate
        for i, r in enumerate(rows):
            if len(r) > 8 and r[8] == "folder" and isinstance(r[7], int) and not isinstance(r[7], bool):
                self._src.setdefault((self.names[i], int(r[7])), []).append(i)
        self._excl: Dict[Tuple[str, int], str] = {}
        for e in d.get("excluded") or []:
            try:
                self._excl[(wall_name_stub(e[0]), int(e[2]))] = str(e[1])
            except Exception:
                continue

    def __len__(self):
        return len(self.hashes)

    def source(self, path, nbytes, h: int) -> Dict:
        """The SOURCE GATE (10-09): is the file Windows names as this monitor's picture (TranscodedImageCache*: its path
        and byte size) a file this index holds, and how far is the shown picture from it?  -> {"src": name stub,
        "src_code": ok | no_source | other_folder | excluded | new_file, "src_bits", "src_tiers"}. A file added to the
        folder after the index was built is 'new_file' whatever its pixels look like: never 'her' until reindexed."""
        if not path or not isinstance(nbytes, int) or isinstance(nbytes, bool) or nbytes <= 0:
            return {"src": "", "src_code": "no_source"}
        stub = wall_name_stub(os.path.basename(str(path)))
        if not self.folder or _wall_dir(os.path.dirname(str(path))) != _wall_dir(self.folder):
            return {"src": stub, "src_code": "other_folder"}
        rows = self._src.get((stub, nbytes)) or []
        if not rows:
            return {"src": stub, "src_code": "excluded" if (stub, nbytes) in self._excl else "new_file"}
        return {"src": stub, "src_code": "ok", "src_bits": min((h ^ self.hashes[i]).bit_count() for i in rows),
                "src_tiers": [self.tiers[i] for i in rows]}

    def nearest(self, h: int) -> Dict:
        """The best distance, the pictures at it (at most 4 named), their combined tier, the next distance above it."""
        best, idx, second = 65, [], 65
        for i, ph in enumerate(self.hashes):
            d = (h ^ ph).bit_count()
            if d < best:
                best, idx, second = d, [i], best
            elif d == best:
                idx.append(i)
            elif d < second:
                second = d
        return {"names": [self.names[i] for i in idx[:4]], "bits": best, "runner": second,
                "tier": wall_worst(self.tiers[i] for i in idx) if idx else "unknown",
                "named": any(self.named[i] for i in idx)}


def wall_rect(style: str, img_aspect: float, screen_aspect: float):
    """Where the wallpaper picture shows on the primary screen (fractions), and how much of the picture is on screen.
    fit: the whole picture, letter/pillar-boxed (Ace's, 10-06); fill: the screen, the picture cropped; stretch: the screen."""
    a, s = max(1e-6, float(img_aspect)), max(1e-6, float(screen_aspect))
    if style == "fit":
        if a <= s:
            w = a / s
            return (0.5 - w / 2, 0.0, 0.5 + w / 2, 1.0), 1.0
        h = s / a
        return (0.0, 0.5 - h / 2, 1.0, 0.5 + h / 2), 1.0
    if style == "fill":
        return (0.0, 0.0, 1.0, 1.0), min(a / s, s / a)
    if style == "stretch":
        return (0.0, 0.0, 1.0, 1.0), 1.0
    return None, 0.0


def uncovered_share(rect, covers) -> float:
    """Exact share of `rect` that no rect in `covers` overlaps (screen fractions). A cover that cannot be placed counts
    as covering everything (fails closed)."""
    l, t, r, b = [float(v) for v in rect]
    area = (r - l) * (b - t)
    if not area > 0:
        return 0.0
    cs = []
    for c in covers:
        try:
            cl, ct, cr, cb = [float(v) for v in c]
        except Exception:
            return 0.0
        if not all(math.isfinite(v) for v in (cl, ct, cr, cb)):
            return 0.0
        cl, ct, cr, cb = max(l, cl), max(t, ct), min(r, cr), min(b, cb)
        if cr > cl and cb > ct:
            cs.append((cl, ct, cr, cb))
    if not cs:
        return 1.0
    xs = sorted({l, r, *[c[0] for c in cs], *[c[2] for c in cs]})
    ys = sorted({t, b, *[c[1] for c in cs], *[c[3] for c in cs]})
    covered = 0.0
    for i in range(len(xs) - 1):
        mx = (xs[i] + xs[i + 1]) / 2.0
        for j in range(len(ys) - 1):
            my = (ys[j] + ys[j + 1]) / 2.0
            if any(c[0] <= mx <= c[2] and c[1] <= my <= c[3] for c in cs):
                covered += (xs[i + 1] - xs[i]) * (ys[j + 1] - ys[j])
    return max(0.0, min(1.0, 1.0 - covered / area))


def _reg_read(key: str, name: str):
    """HKCU, read only. None on any failure."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_READ) as k:
            return winreg.QueryValueEx(k, name)[0]
    except Exception:
        return None


def _screen_aspect() -> Optional[float]:
    """The primary screen's width / height (the space windows_now's fractions are in)."""
    try:
        import ctypes
        u = ctypes.windll.user32
        w, h = float(u.GetSystemMetrics(0)), float(u.GetSystemMetrics(1))
        return w / h if w > 0 and h > 0 else None
    except Exception:
        return None


_U32 = {"dll": None}
_U32_LOCK = threading.Lock()


def _input_desktop_is_default() -> Optional[bool]:
    """True: the input desktop is the ordinary one. False: locked / the secure desktop (UAC) has the input (the open is
    refused). None: cannot tell. A private user32 handle, so the shared windll.user32 prototypes are never touched."""
    try:
        import ctypes
        from ctypes import wintypes as wt
        with _U32_LOCK:
            u = _U32["dll"]
            if u is None:
                u = ctypes.WinDLL("user32", use_last_error=True)
                u.OpenInputDesktop.restype = ctypes.c_void_p
                u.OpenInputDesktop.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
                u.CloseDesktop.restype = wt.BOOL
                u.CloseDesktop.argtypes = [ctypes.c_void_p]
                u.GetUserObjectInformationW.restype = wt.BOOL
                u.GetUserObjectInformationW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, wt.DWORD,
                                                        ctypes.POINTER(wt.DWORD)]
                _U32["dll"] = u
        h = u.OpenInputDesktop(0, False, 0x0001)                  # DESKTOP_READOBJECTS
        if not h:
            return False
        try:
            buf = ctypes.create_unicode_buffer(256)
            need = wt.DWORD(0)
            if not u.GetUserObjectInformationW(h, 2, buf, ctypes.sizeof(buf), ctypes.byref(need)):   # UOI_NAME
                return None
            return buf.value.lower() == "default"
        finally:
            u.CloseDesktop(h)
    except Exception:
        return None


class _DiskFS:
    """The real files, read only (tests pass an in-memory stand-in with the same three calls)."""

    @staticmethod
    def isfile(p):
        return os.path.isfile(p)

    @staticmethod
    def key(p):
        st = os.stat(p)
        return (st.st_mtime_ns, st.st_size)

    @staticmethod
    def read(p):
        with open(p, "rb") as f:
            return f.read()


class WallpaperWatch:
    """What the desktop shows, read the way Windows keeps it (HKCU + the files its slideshow transcodes). No screen pixels.
    state() -> {"ok": True, "style", "screen_aspect", "monitors": [{"file", "d", "names", "bits", "runner", "tier",
    "named", "aspect", "src", "src_code", "src_bits", "src_tiers"}]} or {"ok": False, "code", "why"}. Never raises. A file
    is re-fingerprinted only when it changes; its source (the registry) is read on every look."""

    def __init__(self, index_path: Optional[str] = None, themes: Optional[str] = None, reg=None, screen=None, desktop=None,
                 fs=None):
        self.index_path = index_path or os.path.join(os.path.dirname(os.path.abspath(__file__)), WALL_INDEX_FILE)
        self.themes = themes or os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Themes")
        self._reg = reg or _reg_read
        self._screen = screen or _screen_aspect
        self._desktop = desktop or _input_desktop_is_default
        self._fs = fs or _DiskFS
        self._lock = threading.Lock()
        self._fp: Dict[str, Tuple] = {}
        self.index: Optional[WallIndex] = None
        self.index_err: Optional[str] = None
        try:
            self.index = WallIndex(self.index_path)
        except Exception as e:
            self.index_err = "%s: %s" % (type(e).__name__, str(e)[:100])

    def _src(self, fname: str):
        """The source file Windows names for this monitor's picture (TranscodedImageCache*: u32[1] = its byte size, its
        path in UTF-16 from byte 24) -> (path, bytes) or (None, None). Read on EVERY look, never cached with the file:
        the registry and the transcoded file are written separately. Only its name STUB is ever shown."""
        n = "TranscodedImageCache" + ("" if fname == "TranscodedWallpaper" else fname[len("Transcoded"):])
        v = self._reg(_DESK_KEY, n)
        try:
            b = bytes(v)
            if len(b) < 26:
                return None, None
            return b[24:].decode("utf-16-le", "replace").split("\x00")[0], int.from_bytes(b[4:8], "little")
        except Exception:
            return None, None

    def _with_source(self, m: Dict) -> Dict:
        path, nb = self._src(m["file"])
        out = dict(m)
        out.update(self.index.source(path, nb, m["d"]))
        return out

    def _match(self, p: str) -> Optional[Dict]:
        try:
            key = self._fs.key(p)
            with self._lock:
                hit = self._fp.get(p)
            if hit is not None and hit[0] == key:
                return hit[1]
            fp = wall_fingerprint_bytes(self._fs.read(p))
            m = dict(self.index.nearest(fp["d"]))
            fname = os.path.basename(p)
            m.update({"file": fname, "d": fp["d"], "aspect": fp["aspect"]})
            with self._lock:
                self._fp[p] = (key, m)
            return m
        except Exception:
            return None

    def state(self) -> Dict:
        try:
            if self.index is None:
                return {"ok": False, "code": "index", "why": "her slideshow index is unreadable (%s)" % self.index_err}
            bt = self._reg(_WALL_KEY, "BackgroundType")
            if bt != 2:
                return {"ok": False, "code": "not_slideshow",
                        "why": "the desktop background is not the slideshow (BackgroundType %r)" % (bt,)}
            ws, tile = self._reg(_DESK_KEY, "WallpaperStyle"), self._reg(_DESK_KEY, "TileWallpaper")
            style = WALL_STYLES.get(str(ws if ws is not None else "").strip())
            if style is None or str(tile if tile is not None else "0").strip() == "1":
                return {"ok": False, "code": "geometry",
                        "why": "the wallpaper geometry is not modelled (WallpaperStyle %r, TileWallpaper %r)" % (ws, tile)}
            files = [p for p in (os.path.join(self.themes, "Transcoded_%03d" % i) for i in range(16)) if self._fs.isfile(p)]
            if not files:
                p = os.path.join(self.themes, "TranscodedWallpaper")
                files = [p] if self._fs.isfile(p) else []
            if not files:
                return {"ok": False, "code": "no_file", "why": "no transcoded wallpaper file in %s" % self.themes}
            desk = self._desktop()
            if desk is not True:
                return {"ok": False, "code": "locked", "why": ("the screen is locked or on the secure desktop" if desk is False
                                                               else "cannot tell whether the screen is locked")}
            sa = self._screen()
            if not sa:
                return {"ok": False, "code": "screen", "why": "no primary screen size"}
            mons = []
            for p in files:
                m = self._match(p)
                if m is None:
                    return {"ok": False, "code": "unreadable", "why": "%s could not be read" % os.path.basename(p)}
                mons.append(self._with_source(m))
            return {"ok": True, "style": style, "screen_aspect": sa, "monitors": mons}
        except Exception as e:
            return {"ok": False, "code": "error", "why": "wallpaper state error (%s)" % str(e)[:80]}


# ── the score ───────────────────────────────────────────────────────────────────────────────────────────────────
class Gauge:
    """g(t) = g(t0)*exp(-(t-t0)/tau) + w, capped. Thread-safe. Tracks peak and seconds spent at/above `line`."""

    def __init__(self, tau_s: float = 120.0, cap: float = 1.0, line: float = 0.5):
        self._lock = threading.Lock()
        self._g = 0.0
        self._t: Optional[float] = None
        self.tau, self.cap, self.line = float(tau_s), float(cap), float(line)
        self.peak = 0.0
        self._above = 0.0
        self.adds = 0

    def _decayed(self, now: float) -> float:
        g, t = self._g, self._t
        if t is None:
            return 0.0
        return g * math.exp(-max(0.0, now - t) / self.tau)

    def _above_since_last(self, now: float) -> float:
        g, t = self._g, self._t
        if t is None or g < self.line:
            return 0.0
        return min(max(0.0, now - t), self.tau * math.log(g / self.line))

    def add(self, w: float, now: float) -> float:
        with self._lock:
            g = self._decayed(now)
            self._above += self._above_since_last(now)
            g = min(self.cap, g + float(w))
            self._g, self._t = g, now
            self.adds += 1
            if g > self.peak:
                self.peak = g
            return g

    def value(self, now: float) -> float:
        with self._lock:
            return self._decayed(now)

    def above_s(self, now: float) -> float:
        with self._lock:
            return self._above + self._above_since_last(now)


# ── the recogniser: analysis is pure, the decision holds the lock ────────────────────────────────────────────────
class Recogniser:
    T2_FEEDS_SCORE = False     # Ace 10-05: the hair-colour check counts silently until it passes its tests
    TW_FEEDS_SCORE = False     # pictures_v2 (10-06): the wallpaper counts silently; no knob promotes it
    TW_PUBLISHES = False       # ... and is never in a publish list, in any mode

    def __init__(self, index: Optional[PictureIndex], knobs: Optional[Dict] = None, wall=None):
        self.index = index
        self.k = clean_knobs(knobs)
        self._lock = threading.Lock()
        tau = self.k["tau_s"]
        self.score = Gauge(tau, line=self.k["publish_at"])     # THE score: 'a picture of me is on the screen'
        self.name_g = Gauge(tau, line=self.k["publish_at"])    # name references (reported, never 'seeing')
        self.t2_g = Gauge(tau, line=self.k["publish_at"])      # the hair check, shadow
        self._last_pub: Dict[Tuple[str, str, str], float] = {}
        self.totals = self._zero()
        self.window = self._zero()
        self._win_t0: Optional[float] = None
        self.pub_n = 0
        self.wall = wall                                       # WallpaperWatch, built on first use while "wallpaper" is on
        self._wall_fail_t: Optional[float] = None
        self.wall_g = Gauge(tau, line=self.k["publish_at"])    # TW, shadow, tier 'her' only: never the score
        self.tw_totals, self.tw_window = self._tw_zero(), self._tw_zero()
        self._tw_on = False                                    # TW has looked at least once this boot (report section)
        self._tw_last: Optional[Tuple[Tuple[str, ...], float]] = None
        self._tw_said_why: set = set()
        self.say = lambda s: print("[SomaticAvatarFairy] " + s, flush=True)

    @staticmethod
    def _zero() -> Dict:
        return {"cycles": 0, "own_skipped": 0, "t0_titles": 0, "t0_hits": 0, "t1_checked": 0, "t1_cycles": 0,
                "t1_hits": 0, "t1_misses": 0, "t2_looks": 0, "t2_would": 0, "would_publish": 0, "best_bits": 65,
                "hit_stems": {}, "t0_titles_hit": {}, "own_titles": {}}

    @staticmethod
    def _tw_zero() -> Dict:
        return {"looks": 0, "sightings": 0, "episodes": 0, "her": 0, "unknown": 0, "unknown_named": 0, "not_her": 0,
                "names": {}, "not": {}, "best_visible": 0.0}

    def _wall_state(self) -> Dict:
        """IO (registry + files), outside the lock. Never raises."""
        if self.wall is None:
            now = time.time()
            if self._wall_fail_t is not None and now - self._wall_fail_t < 60.0:
                return {"ok": False, "code": "error", "why": "the wallpaper watch could not start"}
            try:
                self.wall = WallpaperWatch()
            except Exception as e:
                self._wall_fail_t = now
                return {"ok": False, "code": "error", "why": "the wallpaper watch could not start (%s)" % str(e)[:80]}
        try:
            return self.wall.state()
        except Exception as e:
            return {"ok": False, "code": "error", "why": "wallpaper state error (%s)" % str(e)[:80]}

    def _wall_look(self, wins: List[Dict], ws: Dict, strip_on: bool) -> Dict:
        """Pure: is a slideshow picture on the desktop, uncovered enough for her to see, and is it known to be her?"""
        k = self.k
        if not isinstance(ws, dict) or not ws.get("ok"):
            ws = ws if isinstance(ws, dict) else {}
            return {"sighting": False, "code": str(ws.get("code") or "error"), "why": str(ws.get("why") or "no wallpaper state")}
        if len(wins) >= WALL_MAP_CAP:
            return {"sighting": False, "code": "map_full",
                    "why": "the window map is full (%d windows): what is behind them is not known" % len(wins)}
        mons = ws.get("monitors") or []
        if not mons:
            return {"sighting": False, "code": "no_file", "why": "no monitor picture"}
        mx = min(int(k["wall_max_bits"]), WALL_MAX_BITS_CAP)
        for m in mons:                                       # the SOURCE GATE (10-09): the file Windows names must be indexed
            sc = str(m.get("src_code") or "no_source")
            if sc != "ok":
                return {"sighting": False, "code": sc if sc in _WALL_SRC_WHY else "no_source",
                        "why": _WALL_SRC_WHY.get(sc, _WALL_SRC_WHY["no_source"]) % (m.get("src") or m.get("file"))}
        for m in mons:                                       # ... and the picture shown must BE that file's picture
            sb = m.get("src_bits")
            if not m.get("names") or sb is None or int(sb) > mx:
                return {"sighting": False, "code": "changed",
                        "why": "a monitor shows a picture %s bits from the indexed file Windows names for it (%s): the "
                               "file changed since it was indexed, or the picture changed between two reads"
                               % (sb, m.get("src") or m.get("file"))}
        covers = [tuple(w.get("frac") or (0.0, 0.0, 1.0, 1.0)) for w in wins] + ([STRIP_BAND] if strip_on else [])
        vis = 1.0
        # Visibility is the PRIMARY screen's: her window map is primary-only (vision_ground clips every window to the
        # primary and drops one wholly off it). Each monitor's picture is placed on the primary's geometry and the least
        # visible decides; the secondary's own coverage is NOT measured -- its picture only adds its tier (wall_worst).
        for m in mons:
            rect, shown = wall_rect(ws.get("style"), m.get("aspect", 1.0), ws.get("screen_aspect", 1.0))
            if rect is None:
                return {"sighting": False, "code": "geometry", "why": "the wallpaper geometry is not modelled"}
            vis = min(vis, uncovered_share(rect, covers) * shown)
        names = []
        for m in mons:
            nm = m.get("src") or m["names"][0]
            if nm not in names:
                names.append(nm)
        out = {"visible": round(vis, 3), "names": names, "bits": max(int(m["src_bits"]) for m in mons),
               "tier": wall_worst(t for m in mons for t in [m.get("tier", "unknown")] + list(m.get("src_tiers") or [])),
               "named": any(m.get("named") for m in mons), "style": ws.get("style"), "files": [m.get("file") for m in mons]}
        if vis < float(k["wall_min_visible"]):
            out.update({"sighting": False, "code": "covered",
                        "why": "covered: %d%% of the wallpaper picture is uncovered (a sighting needs %d%%)"
                               % (int(100 * vis), int(round(100 * float(k["wall_min_visible"]))))})
            return out
        out.update({"sighting": True, "code": "seen", "why": ""})
        return out

    def set_knobs(self, knobs: Dict) -> None:
        with self._lock:
            self.k = clean_knobs(knobs)

    def analyse(self, wins: List[Dict], grab=None, look: Optional[Dict] = None, strip_on: bool = False,
                wall_state: Optional[Dict] = None) -> Dict:
        """Pure: what each channel sees in this frame. `wins` = vision_ground.windows_now() rows, front to back."""
        k = self.k
        own, rows = [], []
        for i, w in enumerate(wins or []):
            why = own_window(w.get("title", ""), w.get("cls", ""))
            rows.append((i, w, why))
            if why:
                own.append((i, tuple(w.get("frac") or (0, 0, 0, 0)), why))
        own_rects = [r for _, r, _ in own] + ([STRIP_BAND] if strip_on else [])
        t0, t1, checked, t0_checked = [], [], 0, 0
        for i, w, why in rows:
            if why:
                continue
            t0_checked += 1
            n = name_in(w.get("title", ""))
            if n:
                t0.append({"title": str(w.get("title", ""))[:120], "name": w.get("name", ""), "matched": n})
        if grab is not None and self.index is not None and len(self.index):
            GW, GH = grab.size
            for i, w, why in rows:
                if why or float(w.get("covered", 0.0) or 0.0) >= 0.5:
                    continue
                l, t, r, b = [float(v) for v in (w.get("frac") or (0, 0, 0, 0))]
                x0, y0, x1, y1 = int(l * GW), int(t * GH), int(r * GW), int(b * GH)
                if x1 - x0 < 64 or y1 - y0 < 64:
                    continue
                crop = grab.crop((x0, y0, x1, y1))
                blanks = [rr for j, rr, _ in own if j < i] + ([STRIP_BAND] if strip_on else [])
                if blanks:
                    from PIL import ImageDraw
                    crop = crop.copy()
                    d = ImageDraw.Draw(crop)
                    for bl, bt, br, bb in blanks:
                        ix0, iy0 = max(x0, int(bl * GW)), max(y0, int(bt * GH))
                        ix1, iy1 = min(x1, int(br * GW)), min(y1, int(bb * GH))
                        if ix1 > ix0 and iy1 > iy0:
                            d.rectangle((ix0 - x0, iy0 - y0, ix1 - x0 - 1, iy1 - y0 - 1), fill=(128, 128, 128))
                m = match_crop(self.index, crop)
                checked += 1
                m.update({"title": str(w.get("title", ""))[:120], "name": w.get("name", ""),
                          "hit": m["stem"] is not None and m["bits"] <= int(k["t1_max_bits"])})
                t1.append(m)
        t2 = t2_from_look(look, own_rects) if look is not None else None
        res = {"own": [{"title": str(wins[i].get("title", ""))[:80], "why": why} for i, _, why in own],
               "t0": t0, "t0_checked": t0_checked, "t1": t1, "t1_checked": checked, "t2": t2}
        if wall_state is not None:                           # TW: only while "wallpaper" is on (else: no key at all)
            res["wall"] = self._wall_look(list(wins or []), wall_state, strip_on)
        return res

    def decide(self, now: float, a: Dict) -> Dict:
        """Update the score and the counts; say what WOULD be published. Callers publish only in live mode."""
        k = self.k
        with self._lock:
            if self._win_t0 is None:
                self._win_t0 = now
            pubs = []
            hits = [m for m in a.get("t1", []) if m.get("hit")]
            for c in (self.totals, self.window):
                c["cycles"] += 1
                c["own_skipped"] += len(a.get("own", []))
                for o in a.get("own", []):                    # skeptic F5: WHAT was excluded, by title (reported)
                    tk = "%s (%s)" % (str(o.get("title", ""))[:50], o.get("why", ""))
                    c["own_titles"][tk] = c["own_titles"].get(tk, 0) + 1
                c["t0_titles"] += int(a.get("t0_checked", 0))
                c["t0_hits"] += 1 if a.get("t0") else 0
                c["t1_checked"] += int(a.get("t1_checked", 0))
                if a.get("t1_checked"):
                    c["t1_cycles"] += 1
                    c["t1_hits" if hits else "t1_misses"] += 1
                for m in a.get("t1", []):
                    if m.get("bits", 65) < c["best_bits"]:
                        c["best_bits"] = m["bits"]
                for m in hits:
                    c["hit_stems"][m["stem"]] = c["hit_stems"].get(m["stem"], 0) + 1
                for t in a.get("t0", []):
                    c["t0_titles_hit"][t["title"][:60]] = c["t0_titles_hit"].get(t["title"][:60], 0) + 1
                if a.get("t2") is not None:
                    c["t2_looks"] += 1
                    c["t2_would"] += 1 if a["t2"].get("evidence") else 0
            if hits:
                self.score.add(k["w_t1"], now)
            if a.get("t0"):
                self.name_g.add(k["w_t0"], now)
            if a.get("t2") and a["t2"].get("evidence"):
                self.t2_g.add(k["w_t2"], now)
                if self.T2_FEEDS_SCORE:
                    self.score.add(k["w_t2"], now)
            g = self.score.value(now)
            mode = k.get("mode", "shadow")             # shadow's would-publish never delays the first live one
            for m in sorted(hits, key=lambda m: m["bits"]):
                key = (mode, "t1", m["stem"])
                last = self._last_pub.get(key)
                if g >= k["publish_at"] and (last is None or now - last >= k["republish_s"]):
                    self._last_pub[key] = now
                    self.pub_n += 1
                    pubs.append({"topic": "self.visual.recognition", "stem": m["stem"], "bits": m["bits"],
                                 "window": m.get("name") or m.get("title"), "n": self.pub_n, "score": round(g, 3)})
            for t in a.get("t0", []):
                key = (mode, "t0", t["title"].lower())
                last = self._last_pub.get(key)
                if last is None or now - last >= k["t0_republish_s"]:
                    self._last_pub[key] = now
                    pubs.append({"topic": "self.text.reference", "title": t["title"], "window": t.get("name", "")})
            for c in (self.totals, self.window):
                c["would_publish"] += len(pubs)
            out = {"score": round(g, 3), "name": round(self.name_g.value(now), 3),
                   "t2_shadow": round(self.t2_g.value(now), 3), "hits": hits, "publish": pubs}
            w = a.get("wall")
            if w is not None:                                # TW (shadow): counted here, never in `pubs`, never the score
                self._tw_on = True
                line = None
                tier = str(w.get("tier", "unknown"))
                for c in (self.tw_totals, self.tw_window):
                    c["looks"] += 1
                    if w.get("sighting"):
                        c["sightings"] += 1
                        c[tier if tier in WALL_TIERS else "unknown"] += 1
                        if tier == "unknown" and w.get("named"):
                            c["unknown_named"] += 1
                        for nm in w.get("names", []):
                            c["names"][nm] = c["names"].get(nm, 0) + 1
                        c["best_visible"] = max(c["best_visible"], float(w.get("visible", 0.0)))
                    else:
                        cd = str(w.get("code", "error"))
                        c["not"][cd] = c["not"].get(cd, 0) + 1
                if w.get("sighting"):
                    if tier == "her":
                        self.wall_g.add(k["w_t1"], now)
                        if self.TW_FEEDS_SCORE:
                            self.score.add(k["w_t1"], now)
                    key = tuple(w.get("names", []))
                    if self._tw_last is None or self._tw_last[0] != key or now - self._tw_last[1] >= 60.0:
                        for c in (self.tw_totals, self.tw_window):
                            c["episodes"] += 1
                        who = {"her": "her: a file of the slideshow folder Ace labelled hers",
                               "not_her": "NOT her (Ace's label for this file)"}.get(
                            tier, "NOT known to be her (the index does not label this picture)"
                                  + ("; its file name names her (a reference, not evidence)" if w.get("named") else ""))
                        line = ("SELF-IMAGE TW wallpaper (shadow, never said): slideshow picture match %s at %d bits on the "
                                "desktop (%s), %d%% of it uncovered: %s -- counted, not said"
                                % (" / ".join("'%s'" % n for n in w.get("names", [])), int(w.get("bits", 65)),
                                   ", ".join(w.get("files", [])), int(100 * float(w.get("visible", 0.0))), who))
                    self._tw_last = (key, now)
                elif str(w.get("code")) not in self._tw_said_why:
                    self._tw_said_why.add(str(w.get("code")))
                    line = ("SELF-IMAGE TW wallpaper not counted: %s (said once per reason; the report counts every look)"
                            % w.get("why", ""))
                out["wall"] = round(self.wall_g.value(now), 3)
                out["wall_line"] = line
            return out

    def observe(self, now: float, wins: List[Dict], grab=None, look: Optional[Dict] = None,
                strip_on: bool = False) -> Dict:
        ws = self._wall_state() if self.k.get("wallpaper") is True else None     # TW: IO outside the lock
        a = self.analyse(wins, grab, look, strip_on, wall_state=ws)            # the heavy, pure part: outside the lock
        d = self.decide(now, a)
        d["analysis"] = a
        if d.get("wall_line"):
            try:
                self.say(d["wall_line"])
            except Exception:
                pass
        return d

    def report(self, now: float, mode: str) -> Tuple[str, Dict]:
        """The counts since the last report (and in total); resets the window."""
        with self._lock:
            w, self.window = self.window, self._zero()
            t0, self._win_t0 = self._win_t0, now
            tot = json.loads(json.dumps(self.totals))
            tw_on = self._tw_on
            tw_w, self.tw_window = self.tw_window, self._tw_zero()
            tw_tot = json.loads(json.dumps(self.tw_totals))
        span = max(0.0, now - (t0 if t0 is not None else now))
        rec = {"ts": now, "mode": mode, "span_s": round(span, 1), "window": w, "totals": tot,
               "score_now": round(self.score.value(now), 3), "score_peak": round(self.score.peak, 3),
               "score_above_s": round(self.score.above_s(now), 1), "name_now": round(self.name_g.value(now), 3),
               "t2_shadow_now": round(self.t2_g.value(now), 3), "t2_feeds_score": self.T2_FEEDS_SCORE}
        stems = ", ".join("%s x%d" % kv for kv in sorted(w["hit_stems"].items())) or "none"
        titles = ", ".join("'%s' x%d" % kv for kv in sorted(w["t0_titles_hit"].items())[:4]) or "none"
        own_t = ", ".join("'%s' x%d" % kv for kv in sorted(w["own_titles"].items(), key=lambda kv: (-kv[1], kv[0]))[:4]) or "none"
        line = ("SELF-IMAGE report (%s, %.0f s): %d looks, %d own-window skips (%s) | T1 pictures: %d crops in %d looks, "
                "%d hits, %d misses, best %s bits, hits: %s | T0 name (not seeing): %d titles read, %d looks with the name: %s | T2 hair (shadow, "
                "never said): %d looks, %d would-fire | score now %.2f, peak %.2f, %.0f s at/above %.2f | "
                "would publish %d"
                % (mode, span, w["cycles"], w["own_skipped"], own_t, w["t1_checked"], w["t1_cycles"], w["t1_hits"],
                   w["t1_misses"], w["best_bits"] if w["best_bits"] < 65 else "-", stems, w["t0_titles"], w["t0_hits"], titles,
                   w["t2_looks"], w["t2_would"], rec["score_now"], rec["score_peak"], rec["score_above_s"],
                   self.k["publish_at"], w["would_publish"]))
        if tw_on:                                             # TW section only once TW has looked (OFF: as before)
            rec["wallpaper"] = {"window": tw_w, "totals": tw_tot, "wall_her_now": round(self.wall_g.value(now), 3),
                                "wall_her_peak": round(self.wall_g.peak, 3), "feeds_score": self.TW_FEEDS_SCORE,
                                "publishes": self.TW_PUBLISHES}
            nots = ", ".join("%s x%d" % kv for kv in sorted(tw_w["not"].items(), key=lambda kv: (-kv[1], kv[0]))) or "none"
            pics = ", ".join("'%s' x%d" % kv for kv in sorted(tw_w["names"].items(), key=lambda kv: (-kv[1], kv[0]))[:4]) or "none"
            line += (" | TW wallpaper (shadow, never said): %d looks, %d sightings in %d episodes (her %d, not known to be "
                     "her %d [named after her %d], not her %d), best %d%% uncovered, pictures: %s | not counted: %s | "
                     "wall (her) now %.2f"
                     % (tw_w["looks"], tw_w["sightings"], tw_w["episodes"], tw_w["her"], tw_w["unknown"],
                        tw_w["unknown_named"], tw_w["not_her"], int(100 * tw_w["best_visible"]), pics, nots,
                        rec["wallpaper"]["wall_her_now"]))
        return line, rec


# ── her screen, live (V3 only; tests pass a fake) ───────────────────────────────────────────────────────────────
class LiveScreen:
    """windows_now / an in-memory grab / the latest 'hair' look / the hand strip. Every call fails soft."""

    def __init__(self, root: str):
        self.root = root

    def windows(self) -> List[Dict]:
        try:
            from infrastructure import vision_ground as _vg
            return list(_vg.windows_now())
        except Exception:
            return []

    def grab(self):
        try:
            from PIL import ImageGrab
            return ImageGrab.grab().convert("RGB")         # held in memory for one cycle; never saved
        except Exception:
            return None

    def hair_look(self) -> Optional[Dict]:
        try:
            from infrastructure import vision_ground as _vg
            return _vg.cached_look("hair", max_age_s=30.0)
        except Exception:
            return None

    def strip_active(self) -> bool:
        try:
            with open(os.path.join(self.root, "state", "hand_overlay.json"), encoding="utf-8") as f:
                d = json.load(f)
            return bool(d.get("text")) and time.time() <= float(d.get("until") or 0)
        except Exception:
            return False
