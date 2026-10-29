"""eyes_fix2.py -- Ace's second EYES switch, state/eyes_fix2.json (READ ONLY here), and the window-NAME matcher. 2026-10-12
(Nous, nous_builds/eyes_fix2_1012).

Boot K (state/sour_runtime.log L50607-50613): she chose 'look: Sour's Playroom'. The far eye boxed 'Playroom' as 97.5% of a
1024x428 thumbnail of her 3440x1440 screen, ground() called that 'nowhere', and she was told the Playroom "is nowhere on the
screen" -- with the frustration chord -- while the Playroom window sat on her screen and in her own window map
(vision_ground.windows_now). A window's NAME never reached the window map on the look path (vision_camera DESIGN.md L3,
"route window names to look_window", was never built).

WINDOW_NAMES ('window_names'): a phrase that NAMES one window on her screen is answered from the window map, before the far eye:
  * EXACT only. The phrase and a window's key are both reduced to their word sequence (quotes, case, a leading the / my / your /
    her / a / Sour's dropped); the two sequences must be EQUAL. Never a substring (card a-predicate-that-matches-a-substring-
    invents-findings): 'red ball in Sour's Playroom', 'chat with Ace' or 'the Playroom toys' name no window here.
  * A window's keys: its title, its title's head (before ' - '), her map's name for it ("a window called 'Sour's Playroom'",
    "Nous's window (Claude)", with and without the bracket). A title key may also be named with a trailing 'window'
    ("Sour's Playroom window").
  * A phrase (or key) made only of common words -- window, chat, browser, console, screen, Sour, Sourpatches ... -- names
    nothing: 'window', 'the chat', 'my chat window', 'console' fall through to today's path.
  * Several windows with the same key: the front-most, and the answer says it is one of N.
  * Which windows: vision_ground.named_window passes only windows whose CENTRE is on her (primary) screen -- never Ace's.

2026-10-13 (Nous, nous_builds/e1b_1013/vision_hand; Boot L, 10-12 23:17 -> 10-13 12:32) adds two keys to the SAME file:
HAND_REST ('hand_rest'): she is told where her hand rests and what is under it -- one sentence in her percept and in her deed
    ask ("Your hand rests on the title bar of Sour's Playroom (centre of the screen), where you let go of the cursor 42 min
    ago."), and a move to where the hand already is is told as exactly that, with the place (Boot L: 48 of 65 moves were the
    door's bare "it is already there"; the cursor sat 10.7 h on the Playroom's title bar and no line said so).
FRONT_LINE ('front_line'): a window that came to the front of her screen is ONE short line in her next percepts (while it is
    still in front, at most FRONT_LINE_S), never a surprise -- so never the subject of a whole chairman turn -- and it takes no
    glance: what she chose to hold stays held (Boot L L514636 -> L517692: the Playroom's front surprise was queued 11:58, spoken
    as a whole turn ~12:02:50 after the chat window was in front again, and she said "I don't remember making this").

Switch, the same rules as infrastructure/eyes_fix.py (which REJECTS unknown keys, so these keys cannot live there):
    {"window_names": true, "hand_rest": true, "front_line": true}     each key independently ON
    absent file, absent key, false          OFF (today's behaviour)
    not an object, an unknown key, a value that is not true / false, torn JSON
                                            = EVERY key OFF (fail closed), said once per file version in her log
Ace writes the file (with E1b's switch script; this module never writes it); her process only reads it, cached on
(mtime, size). Stdlib only. Revert: the installer's --revert moves this file aside; every eyes_fix2 site then reads OFF (its
import fails closed).
"""
from __future__ import annotations

import json
import os
import re
import threading
from typing import Dict, List, Optional, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
FILE = os.path.join(_ROOT, "state", "eyes_fix2.json")
KEYS = frozenset({"window_names", "hand_rest", "front_line"})
_LOCK = threading.Lock()
_CACHE = {"key": None, "data": {}, "why": "absent", "said": None}


def switch() -> dict:
    """{key: True} for the keys that are ON; {} when the file is absent or malformed. Never raises, never writes."""
    try:
        stt = os.stat(FILE)
    except OSError:
        with _LOCK:
            _CACHE.update(key=None, data={}, why="absent")
        return {}
    key = (stt.st_mtime_ns, stt.st_size)
    with _LOCK:
        if key == _CACHE["key"]:
            return dict(_CACHE["data"])
    data, why = {}, ""
    try:
        with open(FILE, "rb") as f:
            d = json.loads(f.read().decode("utf-8-sig"))
        if not isinstance(d, dict):
            why = "it is not an object"
        elif set(d) - KEYS:
            why = ("unknown keys %s" % ",".join(sorted(map(str, set(d) - KEYS))))[:80]
        elif any(not isinstance(v, bool) for v in d.values()):
            why = "a value is not true / false"
        else:
            data = {k: True for k, v in d.items() if v is True}
    except OSError as e:
        why, key = "it could not be opened (%s)" % type(e).__name__, None
    except Exception as e:
        why = "it is unreadable (%s)" % type(e).__name__
    with _LOCK:
        _CACHE.update(key=key, data=dict(data), why=why or "ok")
        say = bool(why) and _CACHE.get("said") != (why, stt.st_mtime_ns)
        if say:
            _CACHE["said"] = (why, stt.st_mtime_ns)
    if say:
        try:
            print("[EyesFix2] eyes switch eyes_fix2.json: every key OFF (%s)" % why, flush=True)
        except Exception:
            pass
    return dict(data)


def on(key: str) -> bool:
    """One key of Ace's second eyes switch; OFF on any doubt."""
    try:
        return switch().get(str(key)) is True
    except Exception:
        return False


# ── the window-NAME matcher (pure: rows in, a hit out; the tests drive it with scripted rows) ──────────────────────────
_QUOTES = (("‘", "'"), ("’", "'"), ("“", '"'), ("”", '"'), ("´", "'"), ("`", "'"))
_EDGE = " \t.!?,;:\"'()[]{}"
_LEAD_RE = re.compile(r"^(?:the|my|your|her|his|our|their|a|an|this|that|sour'?s|sourpatches'?s?)\s+", re.I)
_HEAD_RE = re.compile(r"\s+[-—–|]\s+")
_PAREN_RE = re.compile(r"\s*\([^()]*\)\s*$")
_TOK_RE = re.compile(r"[a-z0-9]+")
COMMON = frozenset({
    "window", "windows", "chat", "chats", "browser", "console", "terminal", "log", "logs", "ui", "screen", "screens", "desktop",
    "app", "apps", "application", "program", "page", "webpage", "web", "tab", "tabs", "site", "file", "folder", "icon",
    "button", "text", "title", "bar", "front", "back", "open", "new", "main", "own", "thing", "it", "one", "top", "bottom",
    "left", "right", "middle", "side", "corner", "inside", "the", "a", "an", "my", "your", "her", "his", "our", "their", "this",
    "that", "of", "on", "in", "at", "to", "with", "for", "and", "or", "called", "named", "s", "sour", "sours", "sourpatches",
    "ace", "aces"})               # her own name and Ace's are people first: 'look: Sourpatches' is never a window title match
MIN_NAME = 4                  # letters of naming (non-common) words a key / phrase needs: 'Run' or 'Go' name nothing
WINDOW_WORD = "window"


def norm(s) -> str:
    t = str(s or "")
    for a, b in _QUOTES:
        t = t.replace(a, b)
    t = " ".join(t.split()).strip(_EDGE)
    for _ in range(4):
        t2 = _LEAD_RE.sub("", t).strip(_EDGE)
        if t2 == t:
            break
        t = t2
    return t.casefold()


def tokens(s) -> Tuple[str, ...]:
    """The word sequence two names are compared by: 'a window called ‘Sour’s Playroom’' and
    "window called Sour's Playroom" are the same sequence; 'Sour's Playroom' is ('playroom',)."""
    return tuple(_TOK_RE.findall(norm(s)))


def names_something(toks) -> bool:
    """At least MIN_NAME letters of words that are not common words: 'window', 'my chat window', 'console' name nothing."""
    return sum(len(t) for t in toks if t not in COMMON) >= MIN_NAME


def keys_for(w: Dict) -> List[Tuple[Tuple[str, ...], str]]:
    """[(token key, 'title' | 'name')] for one window row; a key that names nothing is never a key."""
    title = " ".join(str(w.get("title") or "").split())
    name = " ".join(str(w.get("name") or "").split())
    out: List[Tuple[Tuple[str, ...], str]] = []
    for src, kind in ((title, "title"), (_HEAD_RE.split(title)[0] if title else "", "title"),
                      (name, "name"), (_PAREN_RE.sub("", name) if name else "", "name")):
        k = tokens(src)
        if k and names_something(k) and (k, kind) not in out:
            out.append((k, kind))
    return out


def label(w: Dict) -> str:
    """Her words for the WINDOW itself ('the Sour's Playroom window'), so a window is never told as a thing inside it."""
    name = " ".join(str(w.get("name") or "").split())
    title = " ".join(str(w.get("title") or "").split())
    if name.startswith("a window called ") and title:
        return "the %s window" % title[:60]
    if name == "your chat window" or name.startswith("Nous's window"):
        return name
    if name.startswith("a browser"):
        return "the browser window" + name[len("a browser"):]
    if name == "a console window":
        return ("the console window '%s'" % _HEAD_RE.split(title)[0][:40]) if title else "the console window"
    if name.startswith("a text window"):
        return "the text window" + name[len("a text window"):]
    return ("the '%s' window" % title[:60]) if title else "that window"


def match_window_name(phrase: str, wins: List[Dict]) -> Optional[Dict]:
    """{'window': row, 'n': how many windows carry that name, 'label', 'key'} for the window the phrase NAMES exactly --
    front-most first (rows come front to back) -- or None. `wins` must already be her-screen-only (vision_ground does it)."""
    p = tokens(phrase)
    if not p or not names_something(p):
        return None
    bare = p[:-1] if (len(p) > 1 and p[-1] == WINDOW_WORD) else None      # "Sour's Playroom window": a title key + 'window'
    hits, key = [], None
    for w in wins or []:
        for k, kind in keys_for(w):
            if k == p or (kind == "title" and bare is not None and k == bare):
                if not any(int(h.get("hwnd") or 0) == int(w.get("hwnd") or 0) for h in hits):
                    hits.append(w)
                    key = key or " ".join(k)
                break
    if not hits:
        return None
    return {"window": hits[0], "n": len(hits), "label": label(hits[0]), "key": key}
