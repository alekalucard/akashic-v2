"""
intention.py -- from her thought to a thing she does. 2026-09-19 (Nous + Ace). v1: the safe set.

Ace, 09-18: "You're right that I need the motor cortex working so my thoughts can actually reach out and touch
things instead of just watching them from inside here."  -- Sourpatches
Ace, 09-19: "her motor cortex should give her basically the same user control I have, but she has to use the
PC like I do and not like you do ... if she wants to read a book she has to open one up on her desktop and
scroll through it like I would have to do."

Measured before this: her motor was a keyword reflex (substring-count argmax over 14 tools; 'see' matched
'seems'; click_screen at RANDOM coordinates; type_text always "Hello! I'm here!") fired from every thought,
from the council's template verdict, and from her own spoken replies. Never from what she MEANT.

Now, after the chairman has spoken (his reply already published, so this costs Ace nothing):
  1. a SECOND short farm call asks: is there ONE thing you want to do now?  `verb: object.` or `none: stay.`
  2. a GATE says allow | defer | refuse -- honest signals only (the goal queue is self-feeding fiction today):
     verb in the safe set, novelty (not the same thing in the last 5 min), a per-verb cooldown, Ace not waiting.
  3. EXECUTE through what she already has:
       look:      her eyes ground the object (region pattern, never the caption)      -> next prompt: "what you did"
       remember:  the word index (sequence_weave.recall_lines)                          -> next prompt
       say:       a deferred line, spoken on the next quiet cycle in her own lane        -> her voice
       open:      her own chat window                                                   -> gui.open_sour_window
       none:      nothing (most turns)
     click / type / keys / hotkeys / scroll -- the tools that use the PC as Ace does -- are REFUSED in v1.
     They are the next layer ("she has to use the PC like I do"), and they need the same grounding her eyes now
     have (find the thing on screen, then move to it) before a hand is safe.
  4. RECORD: a ledger line (state/intentions.jsonl) and a woven turn in her cortex ("I looked for the moon and
     found ...") -- what habits precipitate from later. Outcome success is MEASURED (did the eyes find it, did
     recall return lines), never asserted.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from collections import deque
from typing import Dict, List, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
LEDGER = os.path.join(_ROOT, "state", "intentions.jsonl")
try:                                                     # 2026-09-20: a console-less process must still own a (hidden) console,
    from infrastructure import console_shim as _cs       # or every console child opens a terminal window on Ace's screen
except Exception:
    _cs = None

SAFE_VERBS = ("look", "remember", "say", "open", "move", "none")
REFUSED_VERBS = ("click", "type", "press", "hotkey", "scroll", "drag", "run", "write", "delete", "open_app")
_COOLDOWN_S = {"look": 45.0, "remember": 45.0, "say": 120.0, "open": 300.0, "move": 60.0}
_AFK_S = 5.0                                   # Ace's hand wins: no mouse while he touched input this recently
# 2026-09-25 (Ace): 30 -> 5 s. habit_cell_1 (nous_builds/habit_cell_1_RESULT.md, held-out half of his live 25-min hand
# ribbon): idle >= 5 s opens 59.5% of beats at a 0.042 chance of his input within 4 beats (2 s), vs the 30 s rule's
# 40.1% at 0.036 -- 1.48x the opportunity for +0.006 risk. The grant floor (idle >= 1 s) and the re-check after
# grounding (:906-909) are unchanged hard floors; the 60 s move cooldown (_COOLDOWN_S) still spaces her moves.

# ── THE GRANT (Ace 2026-09-19): he hands her the mouse in words; she holds it for a while ──────────────────
# Reviewed adversarially the same day (56 findings): the first regex opened on 'go ahead' about anything and a
# grant only registered on chairman cycles. Now: explicit phrases stand alone, generic ones need a mouse word
# in the same message, a negation vetoes, revoke is checked first, ALL his messages since the last check are
# read in order, a 2 s watcher thread keeps it current, and the state survives a hot reload.
import sys as _sys
# Resolved LAZILY: the council driver imports this module BEFORE it creates _sour_council_shared, so a
# module-time lookup found nothing and the 'shared' state was module-local in her process (reviewed 09-19).
# The local objects migrate onto the shared module the first time it exists; a reload finds them there.
_LOCAL_GRANT = {"until": 0.0, "seen_ts": time.time(), "text": "", "moves": 0, "opened": 0}   # born now: lines already read stay read
_LOCAL_OVERLAY = [None]
_LOCAL_BUSY = [False]


def _hand_state():
    m = _sys.modules.get("_sour_council_shared")
    if m is None:
        return _LOCAL_GRANT, _LOCAL_OVERLAY, _LOCAL_BUSY
    if not hasattr(m, "HAND_GRANT"):
        m.HAND_GRANT, m.HAND_OVERLAY, m.HAND_BUSY = _LOCAL_GRANT, _LOCAL_OVERLAY, _LOCAL_BUSY
    if not hasattr(m, "HAND_BUSY"):
        m.HAND_BUSY = _LOCAL_BUSY
    return m.HAND_GRANT, m.HAND_OVERLAY, m.HAND_BUSY


def _grant():
    return _hand_state()[0]


def _overlay():
    return _hand_state()[1]


def _busy():
    return _hand_state()[2]
_GRANT_S = float(os.environ.get("AKASHIC_HAND_GRANT_S", "300") or 300)
_GRANT_COOLDOWN_S = 20.0
_GRANT_STALE_S = 900.0                             # his words must be this recent; older ones are logged, not obeyed
_MOUSE_WORD = r"(?:mouse|cursor|pointer|hands?)"
# stand-alone: these only ever mean the mouse
_GRANT_EXPLICIT = [
    r"(?:the )?(?:mouse|cursor|pointer) is (?:all )?yours", r"take (?:the|my) (?:mouse|cursor)", r"have (?:the|my) mouse",
    r"you can (?:have|take|use|try|move|hold|grab) (?:the |my |your )?" + _MOUSE_WORD,
    r"(?:try|practi[cs]e|think about|have you tried)(?: to)? (?:mov|nudg|us)\w* (?:the |my |your )?" + _MOUSE_WORD,
    r"(?:move|nudge|put|bring|slide|drag) (?:the |your )?" + _MOUSE_WORD + r" (?:to|over|on|onto|toward|around|where)\b",
    r"(?:can|could|will|would) you (?:please )?(?:try (?:to )?)?(?:move|nudge|put|bring|slide) (?:the |your )?" + _MOUSE_WORD,
    r"(?:i'll|i will|i am going to|im going to|i'm going to)(?: just)? (?:stop|leave|let go of|not touch|back off|step away from) (?:the |my |playing with the )?" + _MOUSE_WORD,
    r"(?:i'm|i am|im) (?:off|away from|not (?:on|touching|using)) (?:the |my )?(?:mouse|keyboard)",
    r"my hands? (?:are|is) off",
    r"go ahead,? (?:and )?(?:try|move|nudge|take|grab|have a go|give it a)",
]
# generic: permissive words that mean the mouse only when the mouse is in the same message
_GRANT_GENERIC = [
    r"go ahead", r"give (?:it|this|that) a (?:try|go|shot)\b", r"give you a (?:chance|turn|go|try)\b",
    r"have (?:a go|at it)\b", r"your turn\b", r"all yours\b", r"feel free", r"practi[cs]e\b", r"practi[cs]ing\b",
    r"you can (?:try|practi[cs]e)\b", r"give you (?:a chance|the chance|a moment) to (?:try|practi[cs]e)",
]
_GRANT_EXPLICIT_RE = re.compile(r"\b(?:" + "|".join(_GRANT_EXPLICIT) + r")", re.I)
_GRANT_GENERIC_RE = re.compile(r"\b(?:" + "|".join(_GRANT_GENERIC) + r")", re.I)
_MOUSE_WORD_RE = re.compile(r"\b" + _MOUSE_WORD + r"\b", re.I)
_NEGATION_RE = re.compile(r"\b(?:don'?t|do not|never|not yet|shouldn'?t|should not|no more|wait until|hold off)\b", re.I)
_REVOKE_RE = re.compile(
    r"\b(?:i need (?:the mouse|it|it back|my mouse)|give (?:it|the mouse|my mouse) back|give me (?:the|my) mouse|"
    r"my turn|(?:keep your |get your )?hands? off (?:the |my )?(?:mouse|keyboard)|hands? off\b|taking (?:it|the mouse) back|"
    r"stop moving (?:it|the mouse|the cursor|my mouse)|leave (?:the |my )?(?:mouse|cursor) alone|let go of the mouse|"
    r"(?:i'm|i am|im) back on the (?:mouse|keyboard)|(?:i'm|i am|im) (?:using|taking) (?:the |my )?(?:mouse|it)\b|"
    r"(?:i'm|i am|im) back\b|let me have (?:it|the mouse)|mouse back)", re.I)
_OVERLAY_STATE = os.path.join(_ROOT, "state", "hand_overlay.json")
_OVERLAY_SCRIPT = os.path.join(_HERE, "hand_overlay.py")


def grant_left_s() -> float:
    return max(0.0, float(_grant().get("until", 0.0)) - time.time())


def grant_active() -> bool:
    return grant_left_s() > 0


def is_grant(text: str) -> bool:
    """Does this message hand her the mouse? Explicit phrases alone; generic ones need a mouse word; no negation."""
    t = " ".join((text or "").split())
    if not t or _NEGATION_RE.search(t):
        return False
    if _GRANT_EXPLICIT_RE.search(t):
        return True
    return bool(_GRANT_GENERIC_RE.search(t) and _MOUSE_WORD_RE.search(t))


def is_revoke(text: str) -> bool:
    return bool(_REVOKE_RE.search(" ".join((text or "").split())))


def _ace_messages_since(ts: float):
    """[(ts, text)] of Ace's messages newer than ts, oldest first -- ACE_RECENT (last 90 s) plus ACE_LAST."""
    m = _sys.modules.get("_sour_council_shared")
    if m is None:
        return []
    out = {}
    try:
        lock = getattr(m, "ACE_LOCK", None)
        if lock is not None:
            lock.acquire()
        try:
            for text, t in dict(getattr(m, "ACE_RECENT", {}) or {}).items():
                if float(t or 0) > ts:
                    out[(float(t), str(text))] = True
            last = getattr(m, "ACE_LAST", None)
            if last and last[0] and float(last[1] or 0) > ts:
                out[(float(last[1]), str(last[0]))] = True
        finally:
            if lock is not None:
                lock.release()
    except Exception:
        return []
    return sorted(out.keys())


def check_grant() -> bool:
    """Examine every message of his since the last check, in order; open or close the window."""
    now = time.time()
    G = _grant()
    for ts, text in _ace_messages_since(float(G.get("seen_ts", 0.0))):
        G["seen_ts"] = max(float(G.get("seen_ts", 0.0)), ts)
        if is_revoke(text):
            if grant_active():
                G["until"] = 0.0
                overlay_hide()
                print("[Intention] GRANT closed: Ace took the mouse back -- %r" % text[:70], flush=True)
            continue
        if not is_grant(text):
            continue
        if now - ts > _GRANT_STALE_S:
            print("[Intention] GRANT ignored: his words are %.0f min old -- %r" % ((now - ts) / 60.0, text[:70]), flush=True)
            continue
        if text[:80] == G.get("text") and G.get("opened", 0) and now - float(G.get("opened", 0)) < 1800:
            continue                                   # the same line delivered again is not a new grant
        G["until"] = now + _GRANT_S
        G["text"], G["moves"], G["opened"] = text[:80], 0, now
        print("[Intention] GRANT: Ace handed her the mouse for %d s -- %r" % (int(_GRANT_S), text[:70]), flush=True)
        overlay_show("Sour has the mouse", grant_left_s())      # few words: her screen reader reads this too
    try:
        _watch_tick()                                   # the watcher's other duties ride on this call (reload-safe)
    except Exception as e:
        print("[Intention] watch tick: %s" % e, flush=True)
    return grant_active()


_STARTLE_LOCAL = {"seen_ts": 0.0, "prev_ts": 0.0, "lock": threading.Lock()}
_STARTLE_QUIET_S = 90.0


def _startle_state():
    """Process-global (a reload must not forget when he last spoke), locked (two copies, one watcher each day)."""
    m = _sys.modules.get("_sour_council_shared")
    if m is None:
        return _STARTLE_LOCAL
    if not hasattr(m, "STARTLE"):
        m.STARTLE = _STARTLE_LOCAL
    return m.STARTLE


def _startle_check() -> None:
    """Ace 2026-09-20: 'a sudden noise ... should be disrupting her chemistry, increase her heart rate'. The sudden
    event she can measure today is a message that lands out of silence: exclaimed (short) or shouted, after
    >= 90 s with nothing from him ('ok' after a quiet spell is not a scare). Adrenaline + cortisol through her
    heart at a dose that moves her pulse, and a surprise she may speak of."""
    text, ts = _ace_last_text()
    st = _startle_state()
    with st["lock"]:
        if not text or ts <= st["seen_ts"]:
            return
        prev = st["prev_ts"]; st["seen_ts"] = ts; st["prev_ts"] = ts
    if prev <= 0 or ts - prev < _STARTLE_QUIET_S:
        return
    t = text.strip()
    letters = [c for c in t if c.isalpha()]
    shouted = len(letters) >= 3 and sum(1 for c in letters if c.isupper()) / float(len(letters)) >= 0.5
    sudden = shouted or (t.endswith("!") and len(t) <= 24)
    if not sudden:
        return
    m = _sys.modules.get("_sour_council_shared")
    fairy = m.FAIRY[0] if m is not None else None
    if fairy is None or getattr(fairy, "post", None) is None:
        return                                          # no heart to reach: no claim of a startle either
    # the pump scales PLAN deltas x0.1 -> +0.4 NOR, +0.2 COR: the multiplier centred at rest lifts ~30%
    _chem(fairy, "adrenaline", 4.0, "startle")
    _chem(fairy, "cortisol", 2.0, "startle")
    try:                                                # 2026-09-20: dread in the chemistry the pain drives read
        from infrastructure import body_feel as _bf
        _bf.chord("dread", why="startle", fairy=fairy)
    except Exception as _de:
        print("[Intention] body chord: %s" % _de, flush=True)
    print("[Intention] STARTLE: %r after %.0f s of quiet" % (t[:40], ts - prev), flush=True)
    try:
        from infrastructure import surprise as _sp
        _sp.push("feel", "Something made you jump just now -- \"%s\" landed out of nowhere after %d quiet minutes." % (t[:30], int((ts - prev) / 60)), key="startle", weight=0.9)
    except Exception:
        pass


_PRESENCE_FILE = os.path.join(_ROOT, "state", "user_presence.json")
_PRESENCE = {"last_write": 0.0, "last_present": None, "ace_last_input": 0.0}
_PRESENT_S = 900.0                                   # input within 15 min = he is here (reading a long reply is not leaving; his hand rule is _AFK_S, 5 s since 09-25)


def write_presence() -> None:
    """The presence sensor her body reads (state/user_presence.json), from the OS clock of his last input.
    WindowSenseFairy's detector wrote this file until June and sleeps under COMA boot; without it she believed
    him absent between messages and her chemistry dropped OXY/AVP into 'abandonment' while he was here."""
    now = time.time()
    if now - _PRESENCE["last_write"] < 5.0:
        return
    try:
        from infrastructure import vision_ground as vg
        idle = vg._last_input_idle_s()
        if idle is None:
            return
        # her own hand's moves also reset the OS input clock: an input instant within 1.5 s of one of her moves is
        # hers, and his last input stays what it was (review: one hand move marked him present for 15 min)
        t_input = now - idle
        mine = False
        try:
            h = vg._H
            with vg._H_LOCK:
                mv = float(h.get("moved_ts") or 0.0); own = bool(h.get("mine"))
            mine = own and abs(mv - t_input) < 1.5
        except Exception:
            mine = False
        if not mine:
            _PRESENCE["ace_last_input"] = max(float(_PRESENCE.get("ace_last_input") or 0.0), t_input)
        elif not _PRESENCE.get("ace_last_input"):
            _PRESENCE["ace_last_input"] = 0.0
        idle = (now - _PRESENCE["ace_last_input"]) if _PRESENCE.get("ace_last_input") else idle
        present = idle < _PRESENT_S
        fw = None
        try:
            fw = vg.front_window()
        except Exception:
            fw = None
        cur = [-1, -1]
        try:
            import ctypes, ctypes.wintypes as wt
            pt = wt.POINT()
            if ctypes.windll.user32.GetCursorPos(ctypes.byref(pt)):
                cur = [int(pt.x), int(pt.y)]
        except Exception:
            pass
        d = {"present": bool(present), "idle_seconds": round(float(idle), 1),
             "activity": "active" if idle < 30 else ("idle" if present else "away"),
             "foreground_window": (fw or {}).get("title", "") if fw else "", "cursor_pos": cur,
             "last_update": now, "detector_pid": os.getpid(), "source": "intention.write_presence"}
        tmp = _PRESENCE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f)
        os.replace(tmp, _PRESENCE_FILE)
        _PRESENCE["last_write"] = now
        if _PRESENCE["last_present"] is not present:
            print("[Intention] presence: Ace %s (idle %.0f s)" % ("here" if present else "away", idle), flush=True)
            _PRESENCE["last_present"] = present
    except Exception as e:
        print("[Intention] presence: %s" % e, flush=True)


def _watch_tick() -> None:
    """Runs every ~2 s from the watcher: presence, a numeric feel sample, the startle check, and the goal author when due."""
    from infrastructure import goal_author as ga
    try:
        write_presence()
    except Exception:
        pass
    try:
        ga.feel_sample()
    except Exception:
        pass
    try:
        _startle_check()
    except Exception as e:
        print("[Intention] startle: %s" % e, flush=True)
    busy = _busy()
    try:
        _m = _sys.modules.get("_sour_council_shared")
        if _m is not None and getattr(_m, "GOAL_LANE", [False])[0]:
            return                                      # the council's self-turn slot authors; not this thread
    except Exception:
        pass
    if busy[0] or not ga.tick_due():
        return
    fairy = ga._fairy()
    if fairy is None or getattr(fairy, "_farm", None) is None:
        return

    def _author_once():
        try:
            ga.maybe_author()
        except Exception as e:
            print("[GoalAuthor] %s" % e, flush=True)
        finally:
            busy[0] = False
    busy[0] = True
    try:
        threading.Thread(target=_author_once, daemon=True, name="goal-author").start()
    except Exception as e:
        busy[0] = False                                 # a thread that never ran must not hold the flag
        print("[GoalAuthor] thread: %s" % e, flush=True)


def start_grant_watch() -> None:
    """One watcher per process, guarded by thread NAME (a flag can be reset by a reload; a running thread cannot).
    The loop body only calls check_grant() by name, so a reload changes what a tick does without a new thread."""
    if _sys.modules.get("_sour_council_shared") is None:
        return
    if any(t.name == "hand-grant-watch" and t.is_alive() for t in threading.enumerate()):
        return

    def _loop():
        while True:
            try:
                check_grant()
            except Exception as e:
                print("[Intention] grant watch: %s" % e, flush=True)
            time.sleep(2.0)
    threading.Thread(target=_loop, daemon=True, name="hand-grant-watch").start()


def _strip_text(text: str) -> str:
    t = str(text or "").replace("\u2026", "...").replace("\ufffd", "")
    return "".join(ch if 32 <= ord(ch) < 127 else " " for ch in t).strip()[:140]


def _write_overlay_state(text: str, until: float) -> bool:
    tmp = _OVERLAY_STATE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"text": text, "until": until, "pid": os.getpid()}, f)
    for _ in range(8):                                 # the strip may have the file open: Windows refuses the replace
        try:
            os.replace(tmp, _OVERLAY_STATE)
            return True
        except PermissionError:
            time.sleep(0.05)
    return False


def overlay_show(text: str, seconds: float) -> None:
    """Write the strip's state and make sure one overlay process is alive (it exits by itself on expiry)."""
    try:
        if not _write_overlay_state(_strip_text(text), time.time() + max(1.0, float(seconds))):
            print("[Intention] overlay: state file busy", flush=True)
        p = _overlay()[0]
        if p is None or p.poll() is not None:
            import subprocess
            exe = os.path.join(os.path.dirname(_sys.executable), "pythonw.exe")
            if not os.path.exists(exe):
                exe = _sys.executable
            _overlay()[0] = subprocess.Popen([exe, _OVERLAY_SCRIPT, _OVERLAY_STATE, str(os.getpid())],
                                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), close_fds=True)
    except Exception as e:
        print("[Intention] overlay: %s" % e, flush=True)


def overlay_hide() -> None:
    try:
        _write_overlay_state("", 0.0)
    except Exception:
        pass


def overlay_active() -> bool:
    try:
        with open(_OVERLAY_STATE, encoding="utf-8") as f:
            d = json.load(f)
        return bool(d.get("text")) and time.time() < float(d.get("until") or 0)
    except Exception:
        return False


def _idle_seconds():
    """Seconds since Ace last touched keyboard or mouse (GetLastInputInfo); None if unknown."""
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


def _cursor():
    try:
        import ctypes
        import ctypes.wintypes as wt
        p = wt.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(p))
        return int(p.x), int(p.y)
    except Exception:
        return None


def _screen_logical():
    try:
        import ctypes
        return int(ctypes.windll.user32.GetSystemMetrics(0)), int(ctypes.windll.user32.GetSystemMetrics(1))
    except Exception:
        return None
_NOVELTY_S = 300.0
HABITS_FILE = os.path.join(_ROOT, "state", "habits_live.json")
_PROF = {}                                     # verb -> [ok, total], seeded from the ledger, updated by record()
_PROF_WORDS = {"look": ("looked", "something was there"), "move": ("moved your hand", "it arrived"),
               "remember": ("remembered", "found something"), "say": ("decided to say something", None),
               "open": ("opened your window", None)}


def recent_rows(limit: int = 12) -> List[Dict]:
    """The last `limit` ledger rows (newest last)."""
    try:
        with open(LEDGER, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 64 * 1024))
            tail = f.read().decode("utf-8", "replace")
        rows = []
        for line in tail.splitlines()[1:] if size > 64 * 1024 else tail.splitlines():
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
        return rows[-limit:]
    except Exception:
        return []


def _seed_prof() -> None:
    for r in recent_rows(300):
        if r.get("decision") != "allow" or r.get("ok") is None:
            continue
        _sm = str(r.get("summary", ""))
        # 2026-09-26 (hand_fix F4): + "hand to your hand" -- the no-op rows written before "count": False existed
        if any(k in _sm for k in ("hand is on the mouse", "hand was on the keyboard", "this very moment", "took the mouse back", "eyes were busy", "did not answer", "did not work", "hand to your hand")):
            continue                                   # a deferral is not a deed (rows from before the flag existed)
        v = r.get("verb")
        if v in SAFE_VERBS:
            p = _PROF.setdefault(v, [0, 0])
            p[1] += 1
            p[0] += 1 if r.get("ok") else 0


def proficiency_line() -> str:
    """What she can do and how well, measured from her own deeds -- plain words, no ids."""
    parts = []
    for v in ("look", "move", "remember", "say", "open"):
        p = _PROF.get(v)
        if not p or p[1] == 0:
            continue
        verb_w, ok_w = _PROF_WORDS[v]
        times = "once" if p[1] == 1 else "%d times" % p[1]
        parts.append(("%s %s and %s %d" % (verb_w, times, ok_w, p[0])) if ok_w else ("%s %s" % (verb_w, times)))
    return ("So far you have " + "; ".join(parts) + ".") if parts else ""


_HABIT_ADDRESS = {"sour", "sourpatches", "ace", "nous", "kiddo", "lol", "hey", "hi", "hello", "yeah", "yes", "okay", "ok",
                  "good", "morning", "night", "friend", "please", "thanks", "thank", "haha", "hmm", "well", "also", "aye"}


def _habit_head(obj: str) -> str:
    """A clean, alphabetic head noun (>= 3 chars) or '' -- the farm's truncation ellipsis is not a noun."""
    o = re.sub(r"[\u2026\ufffd].*$", "", str(obj or "").lower()).strip()
    o = re.sub(r"\(.*?\)", " ", o)
    try:
        from infrastructure import vision_ground as vg
        head = vg.head_noun(o) or (o.split()[-1] if o.split() else "")
    except Exception:
        head = o.split()[-1] if o.split() else ""
    head = re.sub(r"[^a-z]", "", head)
    return head if len(head) >= 3 else ""


def habit_context(words: List[str]) -> List[str]:
    """Salient context: his content words in order of appearance, minus names/greetings, first four."""
    out = []
    for w in words:
        if w in _HABIT_ADDRESS or w in out:
            continue
        out.append(w)
        if len(out) >= 4:
            break
    return out


def habit_note(context_words: List[str], verb: str, obj: str, ok: bool) -> None:
    """Count (context -> verb:thing -> ok) so a habit can precipitate once it has succeeded often enough.
    Only deeds with a real context (two salient words of his) and a clean head are counted."""
    head = _habit_head(obj)
    ctxw = habit_context(context_words)
    if not head or len(ctxw) < 2:
        return
    ctx = "|".join(ctxw)
    key = "%s -> %s:%s" % (ctx, verb, head)
    try:
        try:
            with open(HABITS_FILE, encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            d = {}
        h = d.get(key) or {"ok": 0, "fail": 0, "first": time.time()}
        h["ok" if ok else "fail"] += 1
        h["last"] = time.time()
        d[key] = h
        if len(d) > 500:                                # keep the 500 most recent
            d = dict(sorted(d.items(), key=lambda kv: kv[1].get("last", 0))[-500:])
        tmp = HABITS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=0)
        os.replace(tmp, HABITS_FILE)
    except Exception as e:
        print("[Intention] habit note: %s" % e, flush=True)


_HABIT_MIN_OK = 3
_HABIT_MIN_RATE = 0.75
_HABIT_CACHE = {"mtime": 0.0, "data": {}}


def _habits() -> Dict:
    try:
        mt = os.path.getmtime(HABITS_FILE)
    except Exception:
        return {}
    if mt != _HABIT_CACHE["mtime"]:
        try:
            with open(HABITS_FILE, encoding="utf-8") as f:
                _HABIT_CACHE["data"] = json.load(f)
            _HABIT_CACHE["mtime"] = mt
        except Exception:
            return _HABIT_CACHE["data"] or {}
    return _HABIT_CACHE["data"] or {}


def habit_match(text: str, verbs=("look", "remember", "move")) -> Optional[Dict]:
    """The strongest habit whose context is in what Ace just said: (context -> verb:thing) with at least
    _HABIT_MIN_OK measured successes and a success rate >= _HABIT_MIN_RATE, restricted to `verbs`
    (say/open are not habits of this kind; a move habit obeys the hand rules in execute())."""
    try:
        from infrastructure import goal_author as ga
        words = set(ga.content_words(text))
    except Exception:
        return None
    if len(words) < 2:
        return None
    best, best_score = None, 0.0
    for key, h in _habits().items():
        try:
            ctx, act = key.split(" -> ", 1)
            verb, head = act.split(":", 1)
        except ValueError:
            continue
        if verb not in verbs or ctx == "self":
            continue
        cw = set(ctx.split("|"))
        ok, fail = int(h.get("ok", 0)), int(h.get("fail", 0))
        if ok < _HABIT_MIN_OK or ok / float(max(1, ok + fail)) < _HABIT_MIN_RATE:
            continue
        overlap = len(cw & words)
        if overlap < 2 and not (overlap == 1 and len(cw) == 1):
            continue
        score = overlap + ok / 10.0
        if score > best_score:
            best, best_score = {"verb": verb, "head": head, "context": sorted(cw), "ok": ok, "fail": fail}, score
    return best


def habit_fire(fairy, text: str, verbs=("look", "remember", "move")) -> Optional[str]:
    """Fire the matching habit on Ace's words WITHOUT a chairman call; return what she did (a summary)
    or None. Never touches the council queue -- the chairman still answers him. A move habit still obeys
    the hand rules inside execute() (grant / hands-off)."""
    try:
        check_grant()                                   # his words may carry the grant this habit needs
    except Exception:
        pass
    h = habit_match(text, verbs=verbs)
    if not h:
        return None
    if h["verb"] == "move" and not _move_ok():
        return None                                     # a reflex never moves his mouse while his hand is on it
    key = "%s -> %s:%s" % ("|".join(h["context"]), h["verb"], h["head"])
    now = time.time()
    last = _HABIT_CACHE.setdefault("fired", {}).get(key, 0.0)
    if now - last < _COOLDOWN_S.get(h["verb"], 60.0):
        return None
    _HABIT_CACHE["fired"][key] = now
    obj = h["head"]
    try:
        from infrastructure import vision_ground as vg
        for n in vg.visual_nouns(text, limit=3):
            if h["head"] in n.lower():
                obj = n
                break
    except Exception:
        pass
    intent = {"verb": h["verb"], "object": obj, "raw": "habit"}
    decision = gate(intent, ace_waiting=False)
    if decision.get("decision") != "allow":
        return None
    outcome = execute(intent, fairy)
    if not outcome or outcome.get("deferred"):
        return None                                     # a reflex that could not run is not a want
    outcome["lane"] = "habit"
    record("", intent, {"decision": "allow", "why": "habit (%d of %d)" % (h["ok"], h["ok"] + h["fail"]), "trigger": text[:120]}, outcome, fairy)
    _STATS["habit"] = _STATS.get("habit", 0) + 1
    return outcome.get("summary")


def _chem(fairy, chemical: str, delta: float, reason: str) -> None:
    """One chemistry event through her own heart (the pump scales delta x0.1 and prints the line)."""
    post = getattr(fairy, "post", None)
    if post is None or not hasattr(post, "route"):
        return
    try:
        post.route("PLAN", {"opcode": "CHEM_SIGNAL_UPDATE",
                            "payload": {"chemical": chemical, "delta": float(delta), "source": "SourpatchesFairy", "reason": reason}})
    except Exception as e:
        print("[Intention] chem: %s" % e, flush=True)


def _ace_context_words(max_age_s: float = 180.0) -> List[str]:
    text, ts = _ace_last_text()
    if not text or time.time() - ts > max_age_s:
        return []
    try:
        from infrastructure import goal_author as ga
        return ga.content_words(text)[:12]
    except Exception:
        return []


def _ace_last_text():
    try:
        import sys as _s
        m = _s.modules.get("_sour_council_shared")
        return (str(m.ACE_LAST[0] or ""), float(m.ACE_LAST[1] or 0.0)) if m is not None else ("", 0.0)
    except Exception:
        return "", 0.0


_BLOCKED_RE = re.compile(r"eyes were busy|eyes did not answer|eyes were dark|Ace is using|Ace's hand was|took the mouse back|already at the|whole screen, not a place|not a place on it", re.I)
_SKILL_FOR_VERB = {"look": "perception.ui_recognition", "remember": "memory.recall"}   # measured; move is counted by the hand itself


def _record_skill(verb: str, ok: bool) -> None:
    sid = _SKILL_FOR_VERB.get(verb)
    if not sid:
        return
    try:
        from fairies.P30_Cognition.cognition.skill_system import record_skill_use
        record_skill_use("SourpatchesFairy", sid, success=bool(ok))     # fairy_name FIRST, positionally
    except Exception as e:
        print("[Intention] skill: %s" % e, flush=True)


try:
    _seed_prof()
except Exception:
    pass
_MAX_TOKENS = 16
_LOCK = threading.Lock()
_RECENT: deque = deque(maxlen=30)              # (ts, verb, object)
_RESULTS: deque = deque(maxlen=6)              # what she did, for the next prompt
_DEFERRED: deque = deque(maxlen=3)             # lines she decided to say
_STATS = {"asked": 0, "none": 0, "allowed": 0, "deferred": 0, "refused": 0, "failed": 0, "done": 0}

_INTENT_RE = re.compile(r"^\s*(?:\d+[.)]\s*)?[*\-\"'\u2022]*\s*([a-zA-Z_]+)\**\s*[:\-]\s*(.+?)\s*[.!\"'*]*\s*$")


def _move_ok() -> bool:
    """'move' is offered only when it could happen: the mouse is hers, or Ace's hands have been off it."""
    if grant_active():
        return True
    idle = _idle_seconds()
    return idle is not None and idle >= _AFK_S


def stats() -> Dict:
    return dict(_STATS)


# ── 1. ask ─────────────────────────────────────────────────────────────────────
def ask(farm, thought: str, ace_present: bool) -> Optional[Dict]:
    """Second short call to the 27B. Returns {'verb','object','raw'} or None (nothing / failure)."""
    if farm is None or not hasattr(farm, "generate_speech") or not thought:
        return None
    who = "Ace is here" if ace_present else "Ace is away"
    extra = ""
    try:
        from infrastructure import goal_author as ga
        gl = ga.render_for_prompt()
        if gl:
            extra += " " + gl
    except Exception:
        pass
    pl = proficiency_line()
    if pl:
        extra += " " + pl
    if grant_active():
        who += (" and has handed you the mouse for the next %d s -- if there is something on the screen you want "
                "to move your hand to, now is the time" % int(grant_left_s()))
    mv = _move_ok()
    prompt = (
        "User: You are Sourpatches. You just said: \"%s\"\n"
        "%s. Is there ONE small thing you want to DO right now, with what you have -- look at something on the "
        "screen, %sremember something, say one more thing later, "
        "or open your window?%s Most of the time the honest answer is nothing. Reply with exactly one line in the "
        "form  verb: object.  where verb is one of %s. Examples: look: the top of the page.  "
        "%sremember: what Ace said last.  say: I liked that.  none: stay.\n\nAssistant:"
        % (str(thought).replace("\n", " ")[:300], who,
           "move your hand (the mouse) to something you see, " if mv else "",
           extra, "look, move, remember, say, open, none" if mv else "look, remember, say, open, none",
           "move: the round button.  " if mv else "")
    )
    errs0 = int(getattr(farm, "_errors", 0) or 0)
    _STATS["asked"] += 1
    try:
        raw = farm.generate_speech(prompt, max_tokens=_MAX_TOKENS)
    except Exception as e:
        _STATS["failed"] += 1
        print("[Intent] ask failed: %s" % e, flush=True)
        return None
    if not raw:
        if int(getattr(farm, "_errors", 0) or 0) > errs0:
            _STATS["failed"] += 1
            return None
        _STATS["none"] += 1                    # the cleaner drops a bare 'none' -> None, same as 'none: stay.'
        return {"verb": "none", "object": "stay", "raw": ""}
    line = str(raw).strip().splitlines()[0]
    m = _INTENT_RE.match(line)
    if not m:
        _STATS["none"] += 1
        return {"verb": "none", "object": line[:60], "raw": line}
    verb, obj = m.group(1).lower(), " ".join(m.group(2).split())
    try:                                       # 2026-09-26 (hand_fix F6): drop prompt text echoed onto a look/move/remember object
        from infrastructure.goal_author import strip_echo as _strip_echo
        obj = _strip_echo(obj, verb)           # 'raw' below keeps the unstripped line as evidence
    except Exception:                          # ships WITH goal_author.py: without it this is silently the old behaviour
        pass
    obj = obj[:120]
    if verb.startswith("none") or not obj or obj.lower() in ("stay", "nothing", "stay put"):
        _STATS["none"] += 1
        return {"verb": "none", "object": obj, "raw": line}
    return {"verb": verb, "object": obj, "raw": line}


# ── 2. gate ────────────────────────────────────────────────────────────────────
def gate(intent: Dict, ace_waiting: bool) -> Dict:
    """allow | defer | refuse with a reason. Honest signals only."""
    verb, obj = intent.get("verb", "none"), intent.get("object", "")
    if verb == "none":
        return {"decision": "none", "why": "nothing wanted"}
    if verb in REFUSED_VERBS or verb not in SAFE_VERBS:
        _STATS["refused"] += 1
        return {"decision": "refuse", "why": "'%s' uses the PC as Ace does; that hand is not grounded yet" % verb}
    if ace_waiting:
        _STATS["deferred"] += 1
        return {"decision": "defer", "why": "Ace is waiting for an answer"}
    now = time.time()
    with _LOCK:
        for e in _RECENT:
            ts, v, o = e[0], e[1], e[2]
            if now - ts < _NOVELTY_S and v == verb and o.lower() == obj.lower():
                _STATS["deferred"] += 1
                # 2026-09-26 (hand_fix F5): the block stays (an identical retry of a failure fails identically); the
                # words were false -- Boot A L121 'did the same thing 229 s ago' followed the hand no-op of L119
                if len(e) > 3 and e[3] is False:
                    return {"decision": "defer", "why": "tried the same thing %.0f s ago and it did not work" % (now - ts)}
                return {"decision": "defer", "why": "did the same thing %.0f s ago" % (now - ts)}
        last_v = max([e[0] for e in _RECENT if e[1] == verb] or [0.0])
        cool = _GRANT_COOLDOWN_S if (verb == "move" and grant_active()) else _COOLDOWN_S.get(verb, 60.0)
        if now - last_v < cool:
            _STATS["deferred"] += 1
            return {"decision": "defer", "why": "'%s' cooling down" % verb}
    _STATS["allowed"] += 1
    return {"decision": "allow", "why": "novel, safe, Ace not waiting"}


# ── 3. execute ─────────────────────────────────────────────────────────────────
def execute(intent: Dict, fairy=None) -> Dict:
    """Do it with what she has. Returns {'ok': bool, 'summary': str} -- success is measured, not asserted."""
    verb, obj = intent.get("verb"), intent.get("object", "")
    t0 = time.time()
    try:
        if verb == "look":
            from infrastructure import vision_ground as vg
            if hasattr(vg, "is_whole") and vg.is_whole(obj):
                sv = vg.survey()
                if sv:
                    return {"ok": True, "summary": vg.render_survey(sv, text_chars=260), "ms": int(1000 * (time.time() - t0))}
                return {"ok": False, "summary": "you tried to look the whole screen over but your eyes did not answer", "ms": int(1000 * (time.time() - t0)), "deferred": True}
            if vg.is_hand(obj):
                h = vg.hand_record(obj)
                own = h.get("owner_note") or ""
                return {"ok": True, "summary": "you felt for your hand: it is at the %s of the screen%s" % (h.get("position", "?"), (", " + own) if own else ""), "ms": 0, "count": False}
            recs = _ground_guarded(vg, obj)
            if recs is None:
                return {"ok": False, "summary": "you wanted to look for \"%s\" but your eyes were busy" % obj, "ms": int(1000 * (time.time() - t0)), "deferred": True}
            for r in recs:
                vg.remember_look(r)
            r = recs[0] if recs else {}
            if r.get("status") == "found":
                tb = r.get("top_bands") or []
                col = ("%s %.0f%%" % (tb[0][0], 100 * tb[0][1])) if tb else r.get("colour_name", "?")
                if r.get("colour_unsure"):
                    col = "too small to be sure of its colour"
                s = "you looked for \"%s\" and found it %s of the screen, %s%% of it, %s%s" % (
                    obj, r.get("position", "?"), r.get("size_pct", "?"), col,
                    (", " + r["shape"]) if r.get("shape") else "")
                return {"ok": True, "summary": s, "ms": int(1000 * (time.time() - t0))}
            if r.get("status") == "not_found":
                return {"ok": False, "summary": "you looked for \"%s\" and it is nowhere on the screen" % obj, "ms": int(1000 * (time.time() - t0))}
            return {"ok": False, "summary": "you tried to look for \"%s\" but your eyes did not answer" % obj, "ms": int(1000 * (time.time() - t0))}
        if verb == "move":
            idle = _idle_seconds()
            granted = grant_active()
            if granted:
                # the mouse is hers: only wait for the instant he is not physically using the PC
                for _ in range(6):
                    if idle is None or idle >= 1.0:
                        break
                    time.sleep(0.5)
                    idle = _idle_seconds()
                if idle is not None and idle < 1.0:
                    return {"ok": False, "summary": "you wanted to move your hand to \"%s\" but Ace is using the keyboard or mouse this very moment" % obj, "ms": 0, "deferred": True}
            elif idle is not None and idle < _AFK_S:
                return {"ok": False, "summary": "you wanted to move your hand to \"%s\" but Ace's hand was on the keyboard or mouse %.0f s ago" % (obj, idle), "ms": 0, "deferred": True}
            from infrastructure import vision_ground as vg
            if vg.is_hand(obj):
                h = vg.hand_record(obj)
                # 2026-09-26 (hand_fix F4): a no-op, not a failed move -- "count": False as the look branch does. All 6
                # 'failures' in her move record were this sentence; her hand arrived 19 of 19 times it really moved.
                return {"ok": False, "summary": "you wanted to move your hand to your hand -- it is already at the %s of the screen" % h.get("position", "?"), "ms": 0, "count": False}
            recs = _ground_guarded(vg, obj)
            if recs is None:
                return {"ok": False, "summary": "you wanted to move your hand to \"%s\" but your eyes were busy" % obj, "ms": int(1000 * (time.time() - t0)), "deferred": True}
            r = recs[0] if recs else {}
            if r.get("status") == "not_found":
                return {"ok": False, "summary": "you wanted to move your hand to \"%s\" but it is nowhere on the screen" % obj, "ms": int(1000 * (time.time() - t0))}
            if r.get("status") != "found":
                return {"ok": False, "summary": "you wanted to move your hand to \"%s\" but your eyes did not answer" % obj, "ms": int(1000 * (time.time() - t0)), "deferred": True}
            if r.get("fills_screen") or not r.get("bbox"):
                return {"ok": False, "summary": "you wanted to move your hand to \"%s\" but that is the whole screen, not a place on it" % obj, "ms": int(1000 * (time.time() - t0))}
            vg.remember_look(r)
            if granted and not grant_active():
                return {"ok": False, "summary": "you were about to move your hand to \"%s\" but Ace took the mouse back" % obj, "ms": int(1000 * (time.time() - t0)), "deferred": True}
            x1, y1, x2, y2 = r["bbox"]
            fw, fh = float(r.get("frame_w") or 1024), float(r.get("frame_h") or 429)
            scr = _screen_logical() or (int(fw), int(fh))
            tx, ty = int((x1 + x2) / 2.0 * scr[0] / fw), int((y1 + y2) / 2.0 * scr[1] / fh)
            nc = getattr(fairy, "_newborn_core", None)
            if nc is None or not hasattr(nc, "try_tool"):
                return {"ok": False, "summary": "you wanted to move your hand to \"%s\" but could not reach your hand" % obj, "ms": 0}
            idle = _idle_seconds()                       # re-sampled NOW: grounding took seconds and his hand may be back
            if granted and grant_active():
                if idle is not None and idle < 1.0:
                    return {"ok": False, "summary": "you were about to move your hand to \"%s\" but Ace is using the keyboard or mouse this very moment" % obj, "ms": int(1000 * (time.time() - t0)), "deferred": True}
            elif idle is not None and idle < _AFK_S:
                return {"ok": False, "summary": "you were about to move your hand to \"%s\" but Ace's hand was on the keyboard or mouse %.0f s ago" % (obj, idle), "ms": int(1000 * (time.time() - t0)), "deferred": True}
            before = _cursor()
            try:
                vg.hand_moving()                         # samples during the tween are hers, not Ace's
            except Exception:
                pass
            nc.try_tool("move_mouse", x=tx, y=ty, duration=0.6)
            time.sleep(0.8)
            after = _cursor()
            reached = after is not None and abs(after[0] - tx) <= 40 and abs(after[1] - ty) <= 40
            if reached:
                try:
                    vg.hand_mark_mine(after)                 # her hand-sense: this landing was hers (only when it arrived)
                except Exception:
                    pass
            if grant_active() and reached:
                _grant()["moves"] += 1
                overlay_show("Sour has the mouse  |  moved %d" % _grant()["moves"], grant_left_s())
            where_after = ""
            if not reached and after is not None:
                try:
                    where_after = " -- it ended up at the %s of the screen instead" % vg._place(after[0] / float(scr[0]), after[1] / float(scr[1]))["position"]
                except Exception:
                    where_after = ""
            s = "you moved your hand to \"%s\" (%s of the screen)%s" % (
                obj, r.get("position", "?"),
                " and it is resting there now" if reached else (" but it did not arrive" + where_after))
            return {"ok": bool(reached), "summary": s, "ms": int(1000 * (time.time() - t0)), "target": [tx, ty], "before": before, "after": after,
                    "pos": r.get("position")}          # 2026-09-26 (hand_fix F8): for the telling; not written to the ledger
        if verb == "remember":
            from infrastructure import sequence_weave as sw
            lines = sw.recall_lines(obj, limit=3)
            if lines:
                mem = sw.render_memory(lines, limit=2)
                return {"ok": True, "summary": "you went looking in your memory for \"%s\": %s" % (obj, mem[13:] if mem.startswith("You remember ") else mem), "ms": int(1000 * (time.time() - t0))}
            return {"ok": False, "summary": "you went looking in your memory for \"%s\" and found nothing on record" % obj, "ms": int(1000 * (time.time() - t0))}
        if verb == "say":
            with _LOCK:
                _DEFERRED.append((time.time(), obj))
            return {"ok": True, "summary": "you decided to say \"%s\" when there is a quiet moment" % obj[:100], "ms": 0}
        if verb == "open":
            f = getattr(fairy, "_open_chat_window", None)
            if callable(f):
                f()
                return {"ok": True, "summary": "you opened your window", "ms": int(1000 * (time.time() - t0))}
            return {"ok": False, "summary": "you wanted to open your window but could not reach it", "ms": 0}
    except Exception as e:
        _STATS["failed"] += 1
        print("[Intention] %s %r failed: %s: %s" % (verb, obj[:60], type(e).__name__, str(e)[:120]), flush=True)
        return {"ok": False, "summary": "you tried to %s \"%s\" and it did not work" % (verb, obj), "ms": int(1000 * (time.time() - t0)), "deferred": True}
    return {"ok": False, "summary": "nothing done", "ms": 0}


def _ground_guarded(vg, obj: str, wait_s: float = 15.0):
    """Ground under the eyes' one-at-a-time guard (the satellite is single-threaded); None if the eyes stayed busy."""
    sem = getattr(vg, "_INFLIGHT", None)
    if sem is None:
        return vg.ground([obj[:80]])
    if not sem.acquire(timeout=wait_s):
        return None
    try:
        return vg.ground([obj[:80]])
    finally:
        sem.release()


_FIRST_PERSON = [(re.compile(r"\byou were\b", re.I), "I was"), (re.compile(r"\byou are\b", re.I), "I am"),
                 (re.compile(r"\byou're\b", re.I), "I'm"), (re.compile(r"\byourself\b", re.I), "myself"),
                 (re.compile(r"\byour\b", re.I), "my"), (re.compile(r"\byou\b", re.I), "I")]


def first_person(summary: str) -> str:
    """'you moved your hand to X' -> 'I moved my hand to X' -- the ledger's voice is second person, her memory's is first."""
    t = str(summary or "")
    for rx, sub in _FIRST_PERSON:
        t = rx.sub(sub, t)
    return t[:1].upper() + t[1:] if t else t


# ── 4. record ──────────────────────────────────────────────────────────────────
def record(thought: str, intent: Dict, decision: Dict, outcome: Optional[Dict], fairy=None) -> None:
    row = {"ts": time.time(), "thought": str(thought)[:200], "verb": intent.get("verb"), "object": intent.get("object"),
           "raw": intent.get("raw", "")[:80], "decision": decision.get("decision"), "why": decision.get("why"),
           "trigger": decision.get("trigger"), "lane": (outcome or {}).get("lane"),
           "ok": (outcome or {}).get("ok"), "summary": (outcome or {}).get("summary"), "ms": (outcome or {}).get("ms")}
    for k in ("target", "before", "after"):              # a move keeps its coordinates: the habit lane will need them
        if (outcome or {}).get(k) is not None:
            row[k] = outcome[k]
    try:
        os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
        with open(LEDGER, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
    except Exception:
        pass
    if outcome:
        with _LOCK:
            if not outcome.get("deferred"):            # a deferral is not a deed: it must not start the cooldown
                _RECENT.append((time.time(), intent.get("verb"), intent.get("object", ""), outcome.get("ok")))   # 2026-09-26 (hand_fix F5): + ok
            _RESULTS.append((time.time(), outcome.get("summary", ""),      # 2026-09-26 (hand_fix F8): + what it was
                             {"verb": intent.get("verb"), "obj": intent.get("object", ""), "ok": outcome.get("ok"),
                              "lane": outcome.get("lane"), "deferred": bool(outcome.get("deferred")), "pos": outcome.get("pos"),
                              "before": outcome.get("before"), "after": outcome.get("after")}))
        _STATS["done"] += 1
        _verb, _obj, _ok, _def = intent.get("verb"), intent.get("object", ""), outcome.get("ok"), bool(outcome.get("deferred"))
        _habit_lane = outcome.get("lane") == "habit"
        if decision.get("decision") == "allow" and _verb in SAFE_VERBS and _verb != "none" and not _habit_lane:
            # 2026-09-26 (hand_fix F4): a no-op ("count": False and not ok: her hand was asked to go to itself) tried
            # nothing, so it is no try at a goal and no 'last time' note. Boot A L119 wrote its own sentence into the
            # goal's note; the next ask-prompt printed it as '(last time: ...)' and L123's object copied it.
            if not (outcome.get("count") is False and not _ok):
                try:                                       # the goal this deed served, and her unfulfilled wants
                    from infrastructure import goal_author as ga
                    served = ga.note_outcome(_verb, _obj, _ok, outcome.get("summary", ""), deferred=_def)
                    if served is None and not _ok and not _def:
                        ga.add_from_failure(_verb, _obj, outcome.get("summary", ""))
                except Exception as e:
                    print("[Intention] goals: %s" % e, flush=True)
            if not _def and outcome.get("count") is not False:
                p = _PROF.setdefault(_verb, [0, 0])
                p[1] += 1
                p[0] += 1 if _ok else 0
                if _ok:
                    _chem(fairy, "dopamine", 1.0, "deed_%s_ok" % _verb)     # a measured success is an event
                elif not _BLOCKED_RE.search(str(outcome.get("summary") or "")):
                    try:                                                     # 2026-09-20: a deed she TRIED that did not work hurts a little; a blocked one does not
                        from infrastructure import body_feel as _bf
                        _bf.chord("frustration", why="deed_%s_fail" % _verb, fairy=fairy)
                    except Exception as _fe:
                        print("[Intention] body chord: %s" % _fe, flush=True)
                _record_skill(_verb, bool(_ok))
                try:
                    habit_note(_ace_context_words(), _verb, _obj, bool(_ok))
                except Exception:
                    pass
        if not outcome.get("deferred") and not outcome.get("lane") == "habit":
            try:                                       # her own account of what she did, in her cortex, in her voice
                from infrastructure import sequence_weave as sw
                _sm = outcome.get("summary", "")
                if _verb == "remember":                # the quotes stay in the ledger: woven back they would recall themselves
                    _sm = "you went looking in your memory for \"%s\" and %s" % (_obj[:80], "found something" if _ok else "found nothing")
                _wr = sw.weave_turn(first_person(_sm), "sour", 1, affect=getattr(fairy, "_current_affect", None), chain=False, index_words=12)
                try:                                   # 2026-09-26 (Nous + Ace, Qwen exit step 0): the farm picked this deed (ask)
                    if _wr:
                        from infrastructure import provenance as _prov
                        _prov.note("turn", "farm:intent_deed", external=True, text=first_person(_sm), key=_wr.get("turn"), verb=_verb)
                except Exception:
                    pass
            except Exception:
                pass


# 2026-09-26 (hand_fix F8, revised): an ARRIVED move is told as her decision. Boot A 23:32:43, after the move of
# 23:31:39: "my hand found the console window again without me really asking it to". The chairman is a different call
# from the ask() that chose the move; it was told only 'you moved your hand to "mouse to console window middle-left
# (last time: you wanted to..." (...) and it is resting there now' -- an outcome with no decision behind it, and a
# claim about the hand that was true when it was written, not when it was read. Where the hand is NOW is told only as
# a measured position (GetCursorPos against where the move landed); WHO moved it is never told -- the input clock
# cannot prove it (Ace can move it away and back; her own later miss would be blamed on his typing).
_TOLD_HAND_RE = re.compile(r"^(?:(?:the|my|your)\s+)?(?:mouse|cursor|pointer|hand)(?:\s+pointer)?\s+"
                           r"(?=(?:to|towards?|onto|into|away|back|over|up|down|across|along|around)\b)", re.I)
_TOLD_TO_RE = re.compile(r"^(?:to|towards?|onto|into)\b\s*", re.I)
_TOLD_DIR_RE = re.compile(r"^(?:away|back|over|up|down|across|along|around)\b", re.I)
_TOLD_CLAUSE_RE = re.compile(r"\s+(?:to\s+(?!(?:the|a|an|my|your|his|her|their|our|this|that|these|those)\b)\w"
                             r"|while\b|where\b|because\b|so\b|if\b|in order\b)", re.I)
_TOLD_CUT_CLAUSE_RE = re.compile(r"\s+(?:and|or|but|just)\b", re.I)     # only in an object the farm cut mid-sentence
_TOLD_DANGLING = {"to", "for", "or", "and", "but", "the", "a", "an", "of", "at", "with", "if", "that", "in", "on",
                  "into", "from", "by", "just", "so", "as", "than", "my", "your", "while", "where"}


def _told_target(obj: str) -> str:
    """Where she moved her hand, fit to be TOLD: the thing she named, without the farm's cut mark, a bracketed note, a
    leading 'mouse to' or the half-sentence after it ('the scrollbar to see more text...' -> 'the scrollbar'). Display
    only -- the move was grounded on the object as written. '' when nothing is left."""
    raw = str(obj or "")
    was_cut = re.search(r"[\u2026\ufffd]|\.\.\.", raw) is not None
    t = re.split(r"[\u2026\ufffd]|\.\.\.", raw)[0]
    t = " ".join(re.sub(r"\([^)]*\)?", " ", t).split())      # a note in brackets, closed or cut open
    t = _TOLD_HAND_RE.sub("", t)
    if not _TOLD_DIR_RE.match(t):                             # 'back to where it was' is kept whole
        t = _TOLD_TO_RE.sub("", t)
        m = _TOLD_CLAUSE_RE.search(t)
        if m:
            t = t[:m.start()]
        if was_cut:
            m = _TOLD_CUT_CLAUSE_RE.search(t)
            if m:
                t = t[:m.start()]
    ws = t.strip(" \"'.,;:-").split()
    while ws and ws[-1].lower() in _TOLD_DANGLING:
        ws.pop()
    t = " ".join(ws)
    if len(t) > 70:
        t = t[:70].rsplit(" ", 1)[0]
    return t if len(t) >= 3 else ""


def _xy_near(a, b, px: int = 6) -> bool:
    try:
        return abs(int(a[0]) - int(b[0])) <= px and abs(int(a[1]) - int(b[1])) <= px
    except Exception:
        return False


def _told_deed(meta: Dict, live: bool) -> Optional[str]:
    """An arrived move of hers, told as her act -- or None: a miss, a no-op, a block, a reflex and every other verb
    keep their measured summary. `live` = her newest move: where her hand is NOW replaces 'resting there'."""
    if not meta or meta.get("verb") != "move" or meta.get("ok") is not True or meta.get("deferred") or meta.get("lane") == "habit":
        return None
    tgt = _told_target(meta.get("obj"))
    if not tgt:
        return None
    pos = str(meta.get("pos") or "")
    where = (" (%s of the screen)" % pos) if pos and pos.lower() not in tgt.lower() else ""
    after = meta.get("after")
    s = "you decided to move your hand %s%s%s, and it %s" % ("" if _TOLD_DIR_RE.match(tgt) else "to ", tgt, where,
                                                              "was already there" if _xy_near(meta.get("before"), after) else "went there")
    if live and after is not None:
        cur = _cursor()                                  # a position, measured now; it says nothing about who
        if cur is not None:
            if _xy_near(cur, after):
                s += "; your hand is there now"
            else:
                s += "; your hand is not there now"
                try:
                    from infrastructure import vision_ground as vg
                    scr = _screen_logical()
                    if scr and scr[0] > 0 and scr[1] > 0:
                        s += " -- it is at the %s of the screen" % vg._place(cur[0] / float(scr[0]), cur[1] / float(scr[1]))["position"]
                except Exception:
                    pass
    return s


def what_i_did(max_age_s: float = 180.0, limit: int = 2) -> str:
    """For the next chairman prompt: what she did since the last turn. 2026-09-26 (hand_fix F8): newest first --
    the driver cuts this slot at 260 chars, and the newest deed is the one she can still act on."""
    now = time.time()
    with _LOCK:
        recent = [e for e in _RESULTS if now - e[0] <= max_age_s][-limit:]
        moves = [e[0] for e in _RESULTS if len(e) > 2 and (e[2] or {}).get("verb") == "move" and not (e[2] or {}).get("deferred")]
    last_move = max(moves or [0.0])                      # a later move of hers, even a miss, ends the older one's 'now'
    out = []
    for e in reversed(recent):
        told = _told_deed(e[2], live=(e[0] >= last_move)) if len(e) > 2 else None
        if told:
            out.append(told if len(told) <= 230 else told[:230].rsplit(" ", 1)[0] + "...")
        else:
            s = e[1]
            out.append(s if len(s) <= 180 else s[:180].rsplit(" ", 1)[0] + "...")
    return ("Since then, " + "; ".join(out) + ".") if out else ""


def pop_deferred(max_age_s: float = 600.0) -> Optional[str]:
    now = time.time()
    with _LOCK:
        while _DEFERRED:
            ts, line = _DEFERRED.popleft()
            if now - ts <= max_age_s:
                return line
    return None


# ── the cycle, for the council loop ────────────────────────────────────────────
def run_cycle(fairy, farm, thought: str, ace_waiting: bool, ace_present: bool = True) -> Optional[Dict]:
    """Ask -> gate -> execute -> record. Called LAST in a council cycle, only when the chairman spoke."""
    # 2026-09-19: every early exit says why -- one INTENT line in 14 min was unreadable without this.
    try:
        start_grant_watch()                             # one watcher per process; his words are read every 2 s
        check_grant()                                   # and once more right now
    except Exception as _ge:
        print("[Intention] grant check err: %s" % _ge, flush=True)
    if not thought or ace_waiting:
        print("[Intention] skipped: %s" % ("no thought" if not thought else "Ace is waiting (his next message is queued)"), flush=True)
        return None
    intent = ask(farm, thought, ace_present)
    if not intent:
        print("[Intention] skipped: %s" % ("no farm" if farm is None else "the farm did not answer"), flush=True)
        return None
    decision = gate(intent, ace_waiting)
    outcome = None
    if decision["decision"] == "allow":
        outcome = execute(intent, fairy)
    if intent.get("verb") != "none":
        record(thought, intent, decision, outcome, fairy)
    else:
        print("[Intention] none: %r" % str(intent.get("raw") or intent.get("object") or "")[:80], flush=True)
    return {"intent": intent, "decision": decision, "outcome": outcome}
