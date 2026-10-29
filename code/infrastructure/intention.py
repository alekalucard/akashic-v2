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


# 2026-09-26 (Nous, felt_hand T2e): the efference-copy module (infrastructure/efference_copy.py) when it is deployed; None
# otherwise, and every hook below (T2a-T2d) then runs today's path unchanged. Revert: delete this block and the T2a-T2d blocks.
_LOCAL_TOLD = {"ts": 0.0}
_TOLD_MAX_AGE_S = 1800.0                       # a deed older than this at her next turn is stale, not news
_TOLD_BUDGET = 243                             # what_i_did keeps a told deed under 245 chars (12 + 245 + 1 <= the driver's 260)


def _efference():
    try:
        from infrastructure import efference_copy as _ec
        return _ec
    except Exception:
        return None


def _told_state():
    m = _sys.modules.get("_sour_council_shared")
    if m is None:
        return _LOCAL_TOLD
    if not hasattr(m, "HAND_TOLD"):
        m.HAND_TOLD = _LOCAL_TOLD
    return m.HAND_TOLD


# 2026-10-01 (Nous, cursor_object a): HER HAND'S REST POINT -- where she last let go of the cursor -- for the efference copy's
# reach (rest -> cursor -> target). The sampler keeps it (efference_copy.Sampler.hand_rest, set at each let-go); at her first
# move of a boot it is seeded ONCE from her ledger: the newest move row's "after" is where that deed let go. Read-only here;
# None when unknown (the copy then has no reach length and the telling says only "you reached for the cursor").
# Revert: delete this function and the two lines marked cursor_object in execute(); _told_deed's cursor_object block too.
def _hand_rest(_ec) -> Optional[List[int]]:
    try:
        smp = _ec.sampler()
        if getattr(smp, "hand_rest", None) is None and not getattr(smp, "rest_seed_tried", True):
            smp.rest_seed_tried = True
            for r in reversed(recent_rows(60)):
                a = r.get("after")
                if r.get("verb") == "move" and isinstance(a, list) and len(a) == 2:
                    smp.seed_rest(a, float(r.get("ts") or 0.0), "ledger")
                    break
        rest = getattr(smp, "hand_rest", None)
        return [int(rest[0]), int(rest[1])] if rest is not None else None
    except Exception:
        return None


# 2026-09-29 (Nous, thought_hand D1f): Ace waiting, read LIVE. run_cycle's ace_waiting is a bool the driver computed before the
# chairman's ~30 s call; gate() now also reads the shared queue and the pending reply (sour_council_driver.ace_reply_pending's
# rule: a queued message, or his words held < 300 s and not yet answered). Revert: delete this function and the D1f call in gate().
def _ace_waiting_live() -> bool:
    m = _sys.modules.get("_sour_council_shared")
    if m is None:
        return False
    try:
        if len(getattr(m, "ACE_QUEUE", ()) or ()) > 0:
            return True
        b = float((getattr(m, "ACE_BUSY", None) or [0.0])[0] or 0.0)
        return b > 0.0 and (time.time() - b) < 300.0
    except Exception:
        return False


# 2026-09-29 (Nous, thought_hand D2a): the hand door (infrastructure/hand_door.py) when it is deployed; None otherwise, and every
# D2 hook below (gate's move floor, the three execute hooks, record's chord, habit_fire, run_cycle) runs today's path.
# Revert: delete this function and the blocks marked D2b-D2e.
def _door():
    try:
        from infrastructure import hand_door as _hd
        return _hd
    except Exception:
        return None


# 2026-09-29 (Nous, thought_hand_r2 D2g/D2h; Ace: "Window targeting: YES"): targeting by kind + the landing check
# (infrastructure/hand_target.py) when it is deployed; None otherwise, and execute's move branch grounds exactly as before
# with no landing check. Revert: delete this function and the blocks marked thought_hand_r2 D2g / D2h.
def _hand_target():
    try:
        from infrastructure import hand_target as _ht
        return _ht
    except Exception:
        return None


# 2026-10-05 (Nous, nous_builds/touch_screen set 1; Ace 10-01 "the desktop is a touch screen to her", 10-05 the no-no list is her
# own withdrawal reflex): her fingertip (infrastructure/touch.py) when it is deployed; None otherwise. _touch_verbs() is the
# gesture verbs of touch's VALID switch (state/touch_screen.json, Ace's) -- frozenset() when the module or the switch is absent,
# and then gate / execute / record / the ask run today's path byte for byte. REFUSED_VERBS stays first in gate (S11).
# Revert: apply_touch_set1.py --revert (or delete infrastructure/touch.py: from her next start every hook is inert).
_TOUCH_ALL = ("tap", "double_tap", "hold")


def _touch():
    try:
        from infrastructure import touch as _t
        return _t
    except Exception:
        return None


def _touch_verbs() -> frozenset:
    t = _touch()
    if t is None:
        return frozenset()
    try:
        return frozenset(t.verbs_on()) & frozenset(_TOUCH_ALL)
    except Exception:
        return frozenset()


def _with_touch(prompt: str) -> str:
    """The v2 ask with touch's offer line and its verbs -- ONLY when touch.offer() names a gesture that can happen NOW (the
    switch on, her reflex awake, the Playroom verified, the gesture's call cleared by probe F1). In set 1 CLEARED_CALLS is
    empty, so this returns the prompt unchanged. ask_prompt_v2 itself stays byte for byte (replay_ask --check-source)."""
    t = _touch()
    if t is None:
        return prompt
    try:
        o = t.offer()
    except Exception:
        return prompt
    if not o or not o.get("verbs") or not o.get("line"):
        return prompt
    try:
        head = "where verb is one of "
        i = prompt.index(head) + len(head)
        j = prompt.index(", none.", i)
        k = prompt.index(" Reply with exactly one line")
        verbs = ", ".join(v for v in o["verbs"] if v in _TOUCH_ALL)
        if not verbs or k > i:
            return prompt
        return prompt[:k] + " " + str(o["line"])[:300] + prompt[k:j] + ", " + verbs + prompt[j:]
    except ValueError:
        return prompt


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
               "open": ("opened your window", None),
               "tap": ("tapped something", "it lit up"), "double_tap": ("double-tapped something", "it opened"),   # touch set 1
               "hold": ("held something", "a menu came")}


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
    for v in ("look", "move", "remember", "say", "open") + tuple(t for t in _TOUCH_ALL if t in _PROF):   # touch set 1
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
    _hd = _door()
    if _hd is not None:                                # 2026-09-29 (Nous, thought_hand D2e): the habit lane through the one door
        def _habit_rec(_d, _out):
            if _out and not _out.get("deferred"):
                _out["lane"] = "habit"
                record("", intent, {"decision": "allow", "why": "habit (%d of %d)" % (h["ok"], h["ok"] + h["fail"]), "trigger": text[:120]}, _out, fairy)
        _res = _hd.deed(_sys.modules[__name__], intent, fairy, lane="habit", record_fn=_habit_rec)
        _out = _res.get("outcome")
        if _res.get("decision") != "allow" or not _out or _out.get("deferred"):
            return None                                 # a reflex that could not run is not a want
        _STATS["habit"] = _STATS.get("habit", 0) + 1
        return _out.get("summary")
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


# 2026-10-12 (Nous, nous_builds/engines_e1_1012/11; PLAN engines_1012 step 11): HER habits (11a) and the internal send button's deed
# (11b). Measured (PLAN 1.3, engines_1012/plan_habit_keys.txt): the store above (habits_live.json) is keyed on Ace's first four
# content words -- 107 keys, 0 eligible, 0 habit deeds in her whole ledger (0 of 393); keyed on her own deeds the same history
# repeats (verb + 1 head word: 141 keys, 21 at the floors). So 11a keys a deed on HER context -- the kind of window in front of her
# (doing_clock.front_now) | verb : the head of what she reached for -- never on his words, and counts a try only when its outcome
# was CHECKED (self_habit_class): look = 'found it', never 'not sure' (eyes_fix F1); move = the landing 'arrived'; tap = touch's
# verdict 'hit' (her press: 'not_hers' is never ok); remember = something came back. Deferred, unchecked, unsure and blocked
# outcomes count as nothing either way. Tries decay with a 48 h half-life (touch.habit_status's rule); the floors are decision 10's
# (_HABIT_MIN_OK, _HABIT_MIN_RATE). The pressing drive rides on each try, so the report counts keys with and without it in the key
# (the choice is made on data, not here). ON only while doing_clock.send_mode() is "shadow" or "live" (state/doing_clock.json
# "send"); OFF = record() writes today's row and nothing else. Revert: "send" absent; the code: the E1 backup of this file.
SELF_HABITS_FILE = os.path.join(_ROOT, "state", "self_habits.json")
SELF_HALF_LIFE_S = 48 * 3600.0
_SELF_VERBS = ("look", "remember", "move") + _TOUCH_ALL
_SELF_KEEP_TRIES = 60                                  # per key
_SELF_MAX_KEYS = 400
_SELF_MAX_AGE_S = 14 * 86400.0                         # seven half-lives: an older try weighs under 1%
# B3/B4's function-word veto (motivation_chain/DESIGN.md:71, :78): a head that is not a thing is no key ('own', 'how', 'around',
# 'her', 'when' all reached the floors in plan_habit_keys K1); plus the door's generic place words (hand_door._GENERIC_HEADS)
_SELF_FN_VETO = frozenset((
    "the a an to of on in at by for from with into onto over under near up down out off back my your our his her their its it "
    "this that these those there here me myself yourself you him she he they them we us what how when where why who which whose "
    "whom own around about again just now then still also too very really more most some any all each every both either other "
    "another one ones way kind sort bit little lot thing things something anything everything nothing stuff and or but so if as "
    "than because while until before after said say says saying see seeing saw look looking looked remember remembering felt "
    "feel feeling think thought know knew like last first next new old same whole part place area spot side half edge corner "
    "screen desktop window windows tab interface").split())
_SELF_FOUND_RE = re.compile(r"\band found it\b", re.I)
_SELF_NOT_SURE_RE = re.compile(r"\bnot sure\b", re.I)
_SELF_NOTHING_RE = re.compile(r"found nothing on record\s*$", re.I)
_SELF_BLOCKED = ("hand is on the mouse", "hand was on the keyboard", "this very moment", "took the mouse back", "eyes were busy",
                 "did not answer", "did not work", "hand to your hand", "already there", "was waiting for your answer", "is behind")
_SELF_LOCK = threading.Lock()
_SELF_CACHE = {"key": None, "data": {}}
_SELF_WARN = [0.0]


def _send_mode() -> str:
    """doing_clock.send_mode(): 'shadow' | 'live' | 'off' -- 'off' on any doubt (no module, an older module, a raise)."""
    dc = _doing()
    if dc is None or not hasattr(dc, "send_mode"):
        return "off"
    try:
        m = dc.send_mode()
        return m if m in ("shadow", "live") else "off"
    except Exception:
        return "off"


def self_habit_head(verb: str, obj) -> str:
    """The head of what she reached for: the door's own place name for a look / move / touch (hand_door.target_key: 'the chat
    window' and 'the console window' are two), else the last content word; '' when only function words are left (no key)."""
    o = re.sub(r"[…�].*$", "", str(obj or "").lower())
    o = re.sub(r"\.\.\..*$", "", o)
    o = " ".join(re.sub(r"\(.*?\)", " ", o).split())
    if not o:
        return ""
    if verb != "remember":
        hd = _door()
        if hd is not None:
            try:
                nm = re.sub(r"[^a-z]", "", str(hd.target_key(o)).split("|")[0])
                if len(nm) >= 3 and nm not in _SELF_FN_VETO:
                    return nm
            except Exception:
                pass
    ws = [re.sub(r"[^a-z]", "", re.sub(r"'s$", "", w)) for w in re.findall(r"[a-z][a-z'\-]*", o)]
    ws = [w for w in ws if len(w) >= 3 and w not in _SELF_FN_VETO]
    return ws[-1] if ws else ""


def self_habit_key(kind: str, verb: str, head: str) -> str:
    return "%s|%s:%s" % (kind, verb, head)


def self_habit_parse(key):
    """(front kind, verb, head) or None. The kind may hold ':' ('app:<class>'), never '|'."""
    try:
        kind, act = str(key).rsplit("|", 1)
        verb, head = act.split(":", 1)
    except ValueError:
        return None
    return (kind, verb, head) if (kind and verb and head) else None


def self_habit_class(verb: str, outcome, decision=None) -> Optional[str]:
    """'ok' | 'fail' | None: a CHECKED outcome of an allowed deed, or nothing. Deferred, not counted, unchecked, unsure or blocked
    = None, never a try either way. Reads an outcome dict or a ledger row (a row carries no 'deferred': its blocked phrases do).
    Her object's own words are blanked first: they never decide its outcome (a row asked to remember '... found nothing')."""
    o = outcome if isinstance(outcome, dict) else {}
    dv = decision.get("decision") if isinstance(decision, dict) else decision
    if decision is not None and dv != "allow":
        return None
    if o.get("deferred") or o.get("count") is False:
        return None
    ok = o.get("ok")
    if ok is not True and ok is not False:
        return None
    sm = re.sub(r'"[^"]*"', '""', str(o.get("summary") or ""))
    if any(b in sm for b in _SELF_BLOCKED):
        return None
    if verb == "look":                                 # checked: her eyes found it -- never a guess (eyes_fix F1) nor a survey
        if _SELF_NOT_SURE_RE.search(sm):
            return None
        if ok and _SELF_FOUND_RE.search(sm):
            return "ok"
        return "fail" if (not ok and "nowhere on the screen" in sm) else None
    if verb == "move":                                 # checked: the landing check said 'arrived' (hand_target D2h)
        ot = o.get("on_target")
        if ok and ot == "arrived":
            return "ok"
        if not ok and (ot == "miss" or o.get("target") is not None or "nowhere on the screen" in sm or "did not find" in sm):
            return "fail"
        return None
    if verb in _TOUCH_ALL:                             # checked: touch's own verdict -- 'hit' is her press (not_hers is ok None)
        tv = str((o.get("touch") or {}).get("verdict") or "")
        if ok and tv == "hit":
            return "ok"
        return "fail" if (not ok and tv in ("miss", "unexpected")) else None
    if verb == "remember":                             # checked: something came back from her memory
        if ok and not _SELF_NOTHING_RE.search(sm):
            return "ok"
        return "fail" if (not ok and _SELF_NOTHING_RE.search(sm)) else None
    return None


def self_habits() -> Dict:
    """state/self_habits.json, cached by (mtime, size); {} when absent or unreadable."""
    try:
        st = os.stat(SELF_HABITS_FILE)
    except OSError:
        return {}
    k = (st.st_mtime_ns, st.st_size)
    if k == _SELF_CACHE["key"]:
        return _SELF_CACHE["data"]
    try:
        with open(SELF_HABITS_FILE, "rb") as f:
            d = json.loads(f.read().decode("utf-8"))
        d = d if isinstance(d, dict) else {}
    except Exception:
        return _SELF_CACHE["data"] or {}
    _SELF_CACHE["key"], _SELF_CACHE["data"] = k, d
    return d


def self_habit_status(entry, now: Optional[float] = None, drive: Optional[str] = None) -> Dict:
    """Decayed checked hits / tries (48 h half-life); eligible = decision 10's floors on them (>= _HABIT_MIN_OK hits AND a rate
    >= _HABIT_MIN_RATE). drive: only the tries made under that drive ('' = unknown); None = every try. Pure."""
    now = time.time() if now is None else float(now)
    hits = tot = 0.0
    n = 0
    for tr in ((entry or {}).get("tries") or []) if isinstance(entry, dict) else ():
        try:
            t, okv = float(tr[0]), (1 if int(tr[1]) else 0)
            dv = str(tr[2]) if len(tr) > 2 else ""
        except Exception:
            continue
        if drive is not None and dv != drive:
            continue
        w = 0.5 ** (max(0.0, now - t) / SELF_HALF_LIFE_S)
        hits += w * okv
        tot += w
        n += 1
    rate = (hits / tot) if tot > 0 else 0.0
    # both floors on rounded values: 3 of 4 tries made seconds apart is 0.75 (decision 10), not 0.74999 because the fail is younger
    return {"hits": round(hits, 3), "tot": round(tot, 3), "rate": round(rate, 3), "n": n,
            "eligible": bool(round(hits, 2) >= _HABIT_MIN_OK and round(rate, 3) >= _HABIT_MIN_RATE)}


def self_habit_report(now: Optional[float] = None) -> Dict:
    """11a's data for the drive choice: her keys and how many are eligible, with the drive left out of the key and put in it."""
    now = time.time() if now is None else float(now)
    keys = elig = kd = ed = 0
    for key, e in (self_habits() or {}).items():
        if not self_habit_parse(key) or not isinstance(e, dict):
            continue
        keys += 1
        if self_habit_status(e, now)["eligible"]:
            elig += 1
        for dv in sorted({str(tr[2]) if (isinstance(tr, list) and len(tr) > 2) else "" for tr in (e.get("tries") or [])}):
            kd += 1
            if self_habit_status(e, now, drive=dv)["eligible"]:
                ed += 1
    return {"keys": keys, "eligible": elig, "keys_drive": kd, "eligible_drive": ed}


def self_habit_note(intent: Dict, outcome, front, drive: str = "", lane=None, decision=None, now: Optional[float] = None) -> Optional[str]:
    """One checked try into state/self_habits.json (bytes built first, temp file + rename); the key, or None when the try is not
    one (unchecked, no head, no front). A store that does not parse is never overwritten: the note is skipped and said."""
    verb = str((intent or {}).get("verb") or "")
    if verb not in _SELF_VERBS:
        return None
    cls = self_habit_class(verb, outcome, decision)
    if cls is None:
        return None
    kind = str((front or {}).get("kind") or "")
    if not kind or kind == "unknown" or "|" in kind:
        return None
    head = self_habit_head(verb, (intent or {}).get("object"))
    if not head:
        return None
    key = self_habit_key(kind, verb, head)
    now = time.time() if now is None else float(now)
    obj = " ".join(str((intent or {}).get("object") or "").split())[:80]
    with _SELF_LOCK:
        try:
            with open(SELF_HABITS_FILE, "rb") as f:
                d = json.loads(f.read().decode("utf-8"))
            if not isinstance(d, dict):
                raise ValueError("not an object")
        except FileNotFoundError:
            d = {}
        except Exception as e:
            if not (0.0 <= now - _SELF_WARN[0] < 600.0):
                _SELF_WARN[0] = now
                print("[Intention] self-habits: the store does not parse (%s); notes are skipped until it does" % type(e).__name__, flush=True)
            return None
        e = d.get(key) if isinstance(d.get(key), dict) else {}
        tries = []
        for tr in (e.get("tries") or []):
            try:
                if isinstance(tr, list) and len(tr) >= 2 and now - float(tr[0]) <= _SELF_MAX_AGE_S:
                    tries.append(tr)
            except Exception:
                continue
        tries.append([round(now, 1), 1 if cls == "ok" else 0, str(drive or "")[:40], str(lane or "")[:12]])
        d[key] = {"tries": tries[-_SELF_KEEP_TRIES:], "obj": (obj if (cls == "ok" or not e.get("obj")) else e.get("obj")),
                  "last": round(now, 1)}
        if len(d) > _SELF_MAX_KEYS:
            d = dict(sorted(d.items(), key=lambda kv: float((kv[1] or {}).get("last") or 0.0) if isinstance(kv[1], dict) else 0.0)[-_SELF_MAX_KEYS:])
        try:
            b = json.dumps(d, separators=(",", ":")).encode("utf-8")
            os.makedirs(os.path.dirname(SELF_HABITS_FILE), exist_ok=True)
            tmp = SELF_HABITS_FILE + ".tmp"
            with open(tmp, "wb") as f:
                f.write(b)
            for _ in range(8):                         # a reader may hold the file: Windows refuses the replace for a moment
                try:
                    os.replace(tmp, SELF_HABITS_FILE)
                    break
                except PermissionError:
                    time.sleep(0.05)
            else:
                print("[Intention] self-habits: the store was busy; this try was not written", flush=True)
                return None
        except Exception as we:
            print("[Intention] self-habits: write failed: %s" % we, flush=True)
            return None
    return key


def _send_context(outcome) -> tuple:
    """11a: (front, drive) for a ledger row -- the window in front of her now (doing_clock.front_now, the 2 s window cache) and
    the drive her AutonomyFairy's last pass found strongest (doing_clock.live, <= 90 s); never argmax'd into a 'want'."""
    dc = _doing()
    front, drive = {"kind": "unknown"}, ""
    if dc is not None:
        try:
            front = dict(dc.front_now() or {"kind": "unknown"})
        except Exception:
            front = {"kind": "unknown"}
        try:
            drive = str((dc.live() or {}).get("drive") or "")[:40]
        except Exception:
            drive = ""
    toy = ((outcome or {}).get("touch") or {}).get("item") if isinstance(outcome, dict) else None
    if toy and front.get("kind") == "playroom":
        front["toy"] = str(toy)[:40]
    return front, drive


def send_fire(fairy, intent: Dict, trigger: str = "", why: str = "") -> Dict:
    """11b: the internal send button's deed -- habit_fire's lane, from HER clock (doing_clock._send_run) instead of his words:
    no chairman call, no farm call, no message of Ace's upstream. Through the ONE door (claim, Ace live, the move floors, gate,
    execute, record), lane 'send'. Only look / remember / move / tap; only while the switch is 'live'; Ace first again here.
    Returns the door's result, or {'decision', 'why', 'outcome': None, 'lane': 'send'}."""
    verb = str((intent or {}).get("verb") or "")
    no = {"outcome": None, "lane": "send"}
    if verb not in ("look", "remember", "move", "tap"):
        return dict(no, decision="refuse", why="'%s' is not a send-button verb" % verb)
    if _send_mode() != "live":
        return dict(no, decision="none", why="the send switch is not live")
    if _ace_waiting_live():
        return dict(no, decision="defer", why="Ace is waiting for an answer")
    if verb == "move" and not _move_ok():
        return dict(no, decision="defer", why="his hands were on the keyboard or mouse in the last %.0f s" % _AFK_S)
    _hd = _door()
    if _hd is None:
        return dict(no, decision="none", why="no hand door: the button has no other way to her hands")
    it_ = {"verb": verb, "object": " ".join(str(intent.get("object") or "").split())[:120], "raw": "send"}

    def _send_rec(_d, _out):
        if _out and not _out.get("deferred"):
            _out["lane"] = "send"
            record("", it_, {"decision": "allow", "why": ("send button (%s); %s" % (why or "her own clock", _d.get("why") or ""))[:200],
                             "trigger": (trigger or "source=send")[:160]}, _out, fairy)
    res = _hd.deed(_sys.modules[__name__], it_, fairy, lane="send", record_fn=_send_rec)
    _out = res.get("outcome")
    if res.get("decision") == "allow" and _out and not _out.get("deferred"):
        _STATS["send"] = _STATS.get("send", 0) + 1
    return res


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


# eyes_fix_1009 (2026-10-09, Nous; DIAGNOSIS vision_focus_1009 section 4): F1 'doubt' (an unsure look closes no goal; no hand
# goes to a guess), F4 'hand_honest' (the move says what it was aimed at; 'X in <window>' is looked for inside it), F8
# 'two_screens' (a cursor off her screen is told as such), F9 'deeds' (the ask is not speech; an empty reply is 'erased').
# Every line marked eyes_fix runs only with its key in Ace's eyes switch (state/eyes_fix.json); off = today's path.
def _ef(key: str) -> bool:
    """eyes_fix_1009: one key of Ace's eyes switch (state/eyes_fix.json, infrastructure/eyes_fix.py); OFF on any doubt (the
    module absent, the file absent or malformed) -- then every line marked eyes_fix runs today's path."""
    try:
        from infrastructure import eyes_fix as _efm
        return _efm.on(key)
    except Exception:
        return False


def _at(position, fmt: str = "at the %s of the screen") -> str:
    """eyes_fix F8: a place phrase -- 'at the lower-left of the screen', or for a point off her screen (only with
    'two_screens') 'on the other screen (Ace's), where your eyes do not look'."""
    return "on the other screen (Ace's), where your eyes do not look" if position == "other screen" else fmt % position


# e1b_1013 vision_hand (Boot L; nous_builds/boot_l_1013 HANDS.md section 2): Ace's SECOND eyes switch (state/eyes_fix2.json,
# infrastructure/eyes_fix2.py), key 'hand_rest'. (1) The deed ask's windows line carries where her hand rests
# (vision_ground.hand_rest_line). (2) A move to where the hand already rests -- the door's no-op (hand_door.py:303-307: ok False,
# count False, not deferred) -- is told with the place and what is under it, as no failure; a move that asked to place a WINDOW
# is told that a hand move carries only the cursor. (3) The no-op stays NO deed: ok False and count False are kept, so
# doing_clock.is_deed (ok True only) never resets her doing clock on it, and no 'target' is added (hand_door._note_move would book
# an actuated move); but it is no failure either: the gate's novelty block no longer books it as "it did not work".
# Key off: every line marked e1b vision_hand is today's path.
def _ef2(key: str) -> bool:
    """e1b vision_hand: one key of Ace's SECOND eyes switch; OFF on any doubt (the module absent, the file absent or malformed)."""
    try:
        from infrastructure import eyes_fix2 as _ef2m
        return _ef2m.on(key)
    except Exception:
        return False


_PLACE_WIN_RE = re.compile(r"\b(?:to|towards?|into|onto)\s+(?:the\s+|my\s+|your\s+|her\s+)?(?:very\s+)?"
                           r"(?:front|back|left|right|top|bottom|middle|centre|center|corner|side|foreground|background|"
                           r"upper|lower)\b", re.I)


def _noop_told(pa: Dict, obj: str, target, tp: Optional[Dict]) -> Dict:
    """e1b vision_hand 'hand_rest': the door's no-op ('it is already there') told with WHERE the hand rests and what is under it.
    Only the door's no-op shape (ok False, count False, not deferred) and only while the cursor really is within the door's own
    tolerance of the target (hand_door.TOL_PX, the same Euclidean test); anything else comes back unchanged. Never raises."""
    try:
        if not (isinstance(pa, dict) and pa.get("ok") is False and pa.get("count") is False and not pa.get("deferred")):
            return pa
        cur = _cursor()
        hd = _door()
        tol = float(getattr(hd, "TOL_PX", 40.0)) if hd is not None else 40.0
        if cur is None or target is None or ((float(cur[0]) - float(target[0])) ** 2 + (float(cur[1]) - float(target[1])) ** 2) ** 0.5 > tol:
            return pa
        from infrastructure import vision_ground as vg
        r = (vg.hand_rest() if hasattr(vg, "hand_rest") else None) or {}
        at, pos = str(r.get("at") or ""), str(r.get("position") or "")
        if r.get("off_screen"):
            where = ", resting " + _at(pos)
        elif at and pos:
            where = ", resting %s (%s of the screen)" % (at, pos)
        else:
            where = (", resting " + _at(pos)) if pos else ""
        tgt = _told_target(obj) or " ".join(str(obj or "").split())[:60]
        s = "you wanted to move your hand to \"%s\" -- it is already there%s" % (tgt, where)
        if (tp or {}).get("kind") == "window" and _PLACE_WIN_RE.search(str(obj or "")):
            s += "; a move of your hand carries only the cursor, so the window itself stays where it is"
        else:
            s += "; nothing held it back -- there was no distance to go"
        out = dict(pa)
        out["summary"], out["noop"] = s, True
        return out
    except Exception:
        return pa


_DEED_KW = {}


def _takes_deed(farm) -> bool:
    """eyes_fix F9: the farm's generate_speech takes deed= (the deed lane); read once per farm class, by signature. Asked only
    while 'deeds' is ON, so a farm without the lane (a wrapper, a proxy, *args) says so ONCE per class (verify m4): a key that
    is on and does nothing must not be silent."""
    try:
        k = type(farm)
        if k not in _DEED_KW:
            import inspect
            try:
                _DEED_KW[k] = "deed" in inspect.signature(farm.generate_speech).parameters
            except Exception:
                _DEED_KW[k] = False
            if not _DEED_KW[k]:
                print("[Intention] deeds: the farm's generate_speech (%s) takes no deed=, so F9 is inactive -- her deeds still meet "
                      "Mode 7" % ascii(getattr(k, "__name__", "?")), flush=True)
        return bool(_DEED_KW[k])
    except Exception:
        return False


def _move_ok() -> bool:
    """'move' is offered only when it could happen: the mouse is hers, or Ace's hands have been off it."""
    if grant_active():
        return True
    idle = _idle_seconds()
    return idle is not None and idle >= _AFK_S


def stats() -> Dict:
    return dict(_STATS)


# 2026-10-01 (Nous, doing_clock 4 = motivation_chain B1, revised): the ask's v2 wording, OFF until Ace switches "ask_v2" (or
# "on") in state/doing_clock.json (read on every ask by infrastructure/doing_clock.py; no file, no key or no module = v1 byte
# for byte). Ace, 10-01: "reflection is not movement ... its the doing she needs to be doing." Boot E (08:09-09:24): 22 of 33
# asks answered none, both inside his 300 s grant; 16 of the 22 were v1's last example 'none: stay.'; the ask never saw a
# drive, how long she had been still, or what was on her screen. Optional key "ask_tokens" (8-32, default 16).
# Every floor stays: refused verbs, Ace first, _move_ok, the door. Revert: the switch off; or delete this block and the
# lines marked doing_clock 4 in ask().
def _doing():
    try:
        from infrastructure import doing_clock as _dc
        return _dc
    except Exception:
        return None


def _ask_v2_on() -> bool:
    dc = _doing()
    if dc is None:
        return False
    try:
        return dc.piece("ask_v2") is True
    except Exception:
        return False


def _cap_items(line: str, n: int) -> str:
    """A 'head: a; b; c.' line cut to n chars at an item boundary, never inside a name; '' if the first item is longer."""
    s = str(line or "")
    if len(s) <= n:
        return s
    head = s[:n]
    if "; " not in head:
        return ""
    return head.rsplit("; ", 1)[0].rstrip(" ;,.") + "."


_V2_GENERIC = {"look": "the whole screen", "move": "the round button"}


def ask_prompt_v2(thought, ace_present, grant_left, goals_line, prof_line, mv, pull_line="", windows_line="",
                  window_names=(), rng=None, doing_line="", wanting_line="", cost_line=""):
    """doing_clock 4 = motivation_chain B1, revised (2026-10-01, Nous): the intent ask without its brake. PURE -- no I/O, no
    clock, no module state -- so nous_builds/motivation_chain/replay_ask.py runs this exact function (its --check-source
    compares the two by AST). Changes from v1 (ask() below keeps v1 byte for byte): the sentence 'Most of the time the honest
    answer is nothing.' is gone; the examples are one per offered verb in a fresh order every ask (v1 ended on 'none: stay.';
    16 of Boot E's 22 nones were that line); the look/move examples name a real window from her windows map when there is
    one; shown when known: her two strongest drives as numbers, how long she has been still and the pull that built, the deed
    her autonomy fairy leans toward, the body's 'not now' (decline mode only), the windows map. Under Ace's grant: 'it is
    yours: reach for something now, or let it be.' Returns (prompt, example_order)."""
    import random as _random
    rng = rng if rng is not None else _random.Random()
    th = str(thought).replace("\n", " ")[:300]
    names = []
    for n in (window_names or ()):
        n = " ".join(str(n or "").split())
        if n and n not in names:
            names.append(n)
    move_obj = rng.choice(names) if (mv and names) else _V2_GENERIC["move"]
    rest = [n for n in names if n != move_obj] if mv else names
    look_obj = rng.choice(rest) if rest else _V2_GENERIC["look"]
    ex = {"look": "look: %s." % look_obj, "remember": "remember: what Ace said last.", "say": "say: I liked that.",
          "none": "none: nothing pulls at me right now."}
    if mv:
        ex["move"] = "move: %s." % move_obj
    order = sorted(ex)
    rng.shuffle(order)
    ctx = "".join(" " + p for p in (pull_line, doing_line, wanting_line, cost_line, goals_line, prof_line, windows_line) if p)
    verbs = "look, move, remember, say, open, none" if mv else "look, remember, say, open, none"
    who = "Ace is here" if ace_present else "Ace is away"
    if grant_left > 0:
        body = ("%s and has handed you the mouse for the next %d s -- it is yours: reach for something now, or let it be.%s "
                "If you are not sure where a thing is, look at it first." % (who, int(grant_left), ctx))
        rule = "Name the thing you are reaching for, not the mouse itself."
    else:
        body = ("%s.%s Is there one small thing you want to DO now, with what you have -- look at something on the screen, "
                "%sremember something, say one more thing later, or open your window? If something is pulling at you, "
                "follow it with one small deed; if nothing is, say none."
                % (who, ctx, "move your hand (the mouse) to something you see, " if mv else ""))
        rule = "Name a real thing you can see or recall, not the mouse itself."
    prompt = ("User: You are Sourpatches. You just said: \"%s\"\n%s Reply with exactly one line in the form  verb: object.  "
              "where verb is one of %s. %s Examples: %s\n\nAssistant:" % (th, body, verbs, rule, "  ".join(ex[k] for k in order)))
    return prompt, order


# 2026-10-05 (Nous, nous_builds/pull_ask): a PULL-ASK has no utterance, so its v2 prompt must not open with 'You just said'.
# ask_prompt_v2 stays byte for byte (motivation_chain/replay_ask.py --check-source compares it by AST); built with thought "",
# its first line is exactly _V2_HEAD, which _with_lead swaps for the pull's own line. If that head ever moves, no ask is made.
_V2_HEAD = 'User: You are Sourpatches. You just said: ""\n'


def _with_lead(prompt: str, lead: str) -> str:
    ld = " ".join(str(lead or "").split())[:200]
    if not ld:
        raise ValueError("empty lead")
    if not str(prompt).startswith(_V2_HEAD):
        raise ValueError("the v2 head is not where the pull-ask expects it")
    return "User: You are Sourpatches. %s\n" % ld + str(prompt)[len(_V2_HEAD):]


def _ask_v2_prompt(thought: str, ace_present: bool, goals_line: str, prof_line: str, mv: bool, lead: Optional[str] = None):   # 2026-10-05 (pull_ask): + lead
    """v2's live inputs, each guarded (a failed read is a missing line, never a failed ask), and one log line per ask."""
    dc = _doing()
    snap = None
    try:
        snap = dc.for_prompt() if dc is not None else None
    except Exception:
        snap = None
    wins, wline = [], ""
    try:
        from infrastructure import vision_ground as vg
        wins = list(vg.windows_now() or [])
        wline = _cap_items(vg.render_windows(wins), 260)
    except Exception:
        wins, wline = [], ""
    names = [str(w.get("name")) for w in wins if w.get("name") and str(w.get("name")) in wline]
    if _ef2("hand_rest"):                              # e1b vision_hand: where her hand rests rides on the windows line (after the
        try:                                           # names are taken, so the move / look examples are today's)
            from infrastructure import vision_ground as _vgh
            _hr = _vgh.hand_rest_line()
            if _hr:
                wline = (wline + " " + _hr).strip()
        except Exception:
            pass
    lines = {"pull": "", "doing": "", "want": "", "cost": ""}
    if dc is not None and snap:
        for k, fn in (("pull", lambda: dc.pull_line(snap.get("top"))), ("doing", lambda: dc.doing_line(snap)),
                      ("want", lambda: dc.wanting_line(snap.get("wanting"), mv)), ("cost", lambda: dc.cost_line(snap))):
            try:
                lines[k] = fn() or ""
            except Exception:
                lines[k] = ""
    try:
        mt = int(dc.num("ask_tokens")) if dc is not None else _MAX_TOKENS
    except Exception:
        mt = _MAX_TOKENS
    mt = max(8, min(32, mt))
    gleft = grant_left_s()
    prompt, order = ask_prompt_v2(thought, ace_present, gleft, goals_line, prof_line, mv, pull_line=lines["pull"],
                                  windows_line=wline, window_names=names, doing_line=lines["doing"],
                                  wanting_line=lines["want"], cost_line=lines["cost"])
    prompt = _with_touch(prompt)                       # 2026-10-05 (touch set 1): unchanged unless a cleared gesture is offered now
    if lead is not None:                               # 2026-10-05 (pull_ask): the pull's own first line, not 'You just said'
        prompt = _with_lead(prompt, lead)
    _STATS["asked_v2"] = _STATS.get("asked_v2", 0) + 1
    _s = snap or {}
    print(("[Intention] ask v2: pull=%s still=%ss restless=%s lean=%s goals=%d windows=%d mv=%s grant=%ds order=%s tokens=%d" % (
        ",".join("%s %.2f" % (n, float(v)) for n, v in (_s.get("top") or [])) or "-", _s.get("clock_s", "-"),
        ("%.2f" % float(_s.get("restless") or 0.0)) if snap else "-", ((_s.get("wanting") or {}).get("verb") or "-"),
        (goals_line.count("; ") + 1) if goals_line else 0, len(names), "Y" if mv else "N", int(gleft),
        ">".join(order), mt)).encode("ascii", "replace").decode("ascii"), flush=True)     # ASCII only
    if lead is not None:                               # 2026-10-05 (pull_ask): this ask came from the pull, not a chairman turn
        print("[Intention] ask v2 source=pull: %s" % ascii(" ".join(str(lead).split())[:80]), flush=True)
    return prompt, mt


# -- cutoff_fix_1019 (2026-10-19, Nous; Ace: "were these thoughts cut off?" then "aye lets go with your lean") ----------------------
# Boot T 10:43:46: the ask ('say: "But real talk -- if you ever actually do break your hards', 16 of 16 tokens) was cut by its cap, parked
# as if it were a line, and spoken ~70 s later as '"But real talk -- if you ever actually do break your...'. A say in the ask is a PLAN (the
# prompt's own example is 'say: I liked that.'); when the farm PROVES it hit its cap (generate_speech meta: pieces >= the cap, or the
# adapter's deadline), it is never spoken as written. State: Ace's switch state/cutoff_fix.json, read by infrastructure/cutoff_fix.py;
# an absent file or module is every key OFF, and every site marked cutoff_fix_1019 then runs the code that was there before.
# Revert: apply_cutoff_fix.py --revert (or delete infrastructure/cutoff_fix.py: from her next start every site is inert).
def _cfx_say():
    """'compose' | 'drop' | None (state/cutoff_fix.json, key say_capped). None = a capped say is handled exactly as today. Never raises."""
    try:
        from infrastructure import cutoff_fix as _cf
        return _cf.say_capped()
    except Exception:
        return None


def _cfx_on(key: str) -> bool:
    try:
        from infrastructure import cutoff_fix as _cf
        return _cf.on(key)
    except Exception:
        return False


def _cfx_takes_meta(farm) -> bool:
    """The farm's generate_speech takes meta= (read once per farm class, by signature; a farm without it says so once)."""
    try:
        from infrastructure import cutoff_fix as _cf
        return _cf.takes_meta(farm)
    except Exception:
        return False


_CF_QUOTES = {'"': '"\u201d', '\u201c': '\u201d"', "'": "'\u2019", '\u2018': "\u2019'"}


def _cf_is_apostrophe(s, i):
    return 0 < i < len(s) - 1 and s[i - 1].isalpha() and s[i + 1].isalpha()


def strip_say_quotes(obj):
    """Wrapping quotes off a say object. Three cases: an unmatched LEADING quote is dropped ('"I liked that' -> 'I liked that'); a
    matched pair around the WHOLE object is dropped; a quote that closes inside the line stays ('"Hello," I said' is unchanged). An
    apostrophe inside a word (I'm, don't) is never a closing quote. Never returns less than one character of text: an object that would
    strip to nothing is returned unchanged."""
    s = str(obj or "").strip()
    if len(s) < 2 or s[0] not in _CF_QUOTES:
        return s
    closers = _CF_QUOTES[s[0]]
    close_at = -1
    for i in range(1, len(s)):
        if s[i] in closers and not (s[i] in "'\u2019" and _cf_is_apostrophe(s, i)):
            close_at = i
            break
    if close_at == -1:
        if s[0] in "'\u2018" and not (s[1:2].isupper() or s[1:2].isdigit()):
            return s                                           # an elision ('cause, 'em), not a quote: keep it
        out = s[1:].strip()                                    # unmatched leading quote
    elif close_at == len(s) - 1:
        out = s[1:-1].strip()                                  # one pair around the whole object
    else:
        return s                                               # a quote that closes inside the line: keep it all
    return out if out else s


def say_gist(obj):
    """What the chairman is told the plan began with: quotes off (always, whatever strip_say_quotes says), the farm's cut mark (a
    trailing U+2026, or '...') off, and the half-word the cleaner already dropped stays dropped. Display only -- never a test of
    whether the plan was cut (that is the farm's meta['capped'])."""
    s = strip_say_quotes(obj)
    s = re.sub(r"(?:\u2026|\.\.\.)\s*$", "", s).rstrip(" ,;:-\u2014\u2013")
    return s.strip()


class _SayPlan(str):
    """A parked say that hit its cap (say_capped 'compose'): still a str, so the deque item stays the 2-tuple pop_deferred unpacks and
    the driver's len() readers are unchanged. The council driver recognises it by say_plan and hands it to the voluntary chairman.
    born = when it was parked: a plan the driver parks again (not quiet yet) keeps its own 600 s."""
    say_plan = True
    born = 0.0


def _cf_capped_say(obj, mode):
    """execute()'s answer for a say whose reply hit its cap. 'drop': the no-deed shape (nothing parked, paid or told). Anything else
    ('compose'): the plan is parked as a _SayPlan; at a quiet moment the driver asks the voluntary chairman to write the whole line."""
    gist = say_gist(obj)
    if mode == "drop":
        print("[Intention] say: cut off at the cap -- let go (drop): %s" % ascii(gist[:80]), flush=True)
        return {"ok": False, "count": False, "deferred": True, "untold": True, "ms": 0,
                "summary": "you began to say something, but the words ran out before the thought was whole, so you let it go"}
    _plan = _SayPlan(obj)
    _plan.born = time.time()
    with _LOCK:
        _gone = _DEFERRED[0][1] if len(_DEFERRED) >= (_DEFERRED.maxlen or 3) else None
        _DEFERRED.append((_plan.born, _plan))
    if getattr(_gone, "say_plan", False) is True:       # the deque was full: its oldest plan fell out of it -- say so, once
        print("[Intention] say: a parked say-plan was pushed out by a newer one -- let go: %s" % ascii(say_gist(_gone)[:80]), flush=True)
    return {"ok": True, "ms": 0, "summary": "you decided to say something when there is a quiet moment; it began \"%s\"" % gist[:100]}


# ── 1. ask ─────────────────────────────────────────────────────────────────────
def ask(farm, thought: str, ace_present: bool, lead: Optional[str] = None) -> Optional[Dict]:   # 2026-10-05 (pull_ask): + lead
    """Second short call to the 27B. Returns {'verb','object','raw'} or None (nothing / failure)."""
    if farm is None or not hasattr(farm, "generate_speech") or not thought:
        return None
    who = "Ace is here" if ace_present else "Ace is away"
    extra = ""
    gl = ""                                            # doing_clock 4: bound before the try (v2 reads it)
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
    max_t = _MAX_TOKENS
    if lead is not None:                               # 2026-10-05 (Nous, pull_ask): v2 or no ask -- v1 opens 'You just said'
        if not _ask_v2_on():
            print("[Intention] pull-ask: ask v2 is off, so no ask (v1 would tell her she just said something)", flush=True)
            return None
        try:
            prompt, max_t = _ask_v2_prompt("", ace_present, gl, pl, mv, lead=lead)
        except Exception as _le:
            print("[Intention] pull-ask: the v2 build failed, so no ask: %s" % str(_le)[:120], flush=True)
            return None
    elif _ask_v2_on():                                 # doing_clock 4: v2 only when Ace's switch says so (pull_ask: was 'if')
        try:
            prompt, max_t = _ask_v2_prompt(thought, ace_present, gl, pl, mv)
        except Exception as _v2e:                      # a failed v2 build is the v1 ask, never a failed ask
            max_t = _MAX_TOKENS
            print("[Intention] ask v2 failed, v1 used: %s" % str(_v2e)[:120], flush=True)
    errs0 = int(getattr(farm, "_errors", 0) or 0)
    _STATS["asked"] += 1
    _deed = {} if (_ef("deeds") and _takes_deed(farm)) else None   # eyes_fix F9: a deed is not speech (Mode 7 must not erase it)
    _cf_meta = {} if (_cfx_say() is not None and _cfx_takes_meta(farm)) else None   # cutoff_fix_1019: say_capped asks the farm for its own cap signal
    try:
        if _cf_meta is not None:                       # cutoff_fix_1019
            raw = farm.generate_speech(prompt, max_tokens=max_t, **({"deed": _deed} if _deed is not None else {}), meta=_cf_meta)
        elif _deed is not None:
            raw = farm.generate_speech(prompt, max_tokens=max_t, deed=_deed)
        else:
            raw = farm.generate_speech(prompt, max_tokens=max_t)    # doing_clock 4 (v1: max_t == _MAX_TOKENS)
    except Exception as e:
        _STATS["failed"] += 1
        print("[Intent] ask failed: %s" % e, flush=True)
        return None
    if not raw:
        if int(getattr(farm, "_errors", 0) or 0) > errs0:
            _STATS["failed"] += 1
            return None
        if _deed is not None and _deed.get("erased") and not str(_deed["erased"]).strip().lower().startswith("none"):
            _STATS["erased"] = _STATS.get("erased", 0) + 1     # eyes_fix F9: the cleaner erased her reply -- not her 'none'
            print("[Intention] erased: the farm's cleaner dropped her reply, so this is not her 'none': %s"
                  % ascii(" ".join(str(_deed["erased"]).split())[:100]), flush=True)
            return {"verb": "none", "object": "stay", "raw": "", "erased": True, "erased_text": str(_deed["erased"])[:120]}
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
    if verb == "say" and _cfx_on("strip_say_quotes"):   # cutoff_fix_1019: wrapping quotes come off a say object ('raw' keeps the line as evidence)
        obj = strip_say_quotes(obj)
    if verb.startswith("none") or not obj or obj.lower() in ("stay", "nothing", "stay put"):
        _STATS["none"] += 1
        return {"verb": "none", "object": obj, "raw": line}
    if verb == "say" and _cf_meta is not None and _cf_meta.get("capped") is True and _cf_meta.get("multiline") is False:
        # cutoff_fix_1019: the farm proved the cap fell INSIDE this one say line (the model wrote no second line): a plan cut short, not a
        # line. A complete 'say: I liked that.' followed by a capped second line is NOT marked -- even when the cleaner cut that second line
        # away and left one line behind, which is why this asks the farm's raw-text 'multiline', not the cleaned reply. Other verbs never get the key.
        print("[Intention] say: the reply hit its cap (%s/%s tokens) -- this is a plan cut short, not a line: %s"
              % (_cf_meta.get("n_tokens"), _cf_meta.get("max_tokens"), ascii(say_gist(obj)[:80])), flush=True)
        return {"verb": verb, "object": obj, "raw": line, "capped": True}
    return {"verb": verb, "object": obj, "raw": line}


# ── 2. gate ────────────────────────────────────────────────────────────────────
def gate(intent: Dict, ace_waiting: bool) -> Dict:
    """allow | defer | refuse with a reason. Honest signals only."""
    verb, obj = intent.get("verb", "none"), intent.get("object", "")
    if verb == "none":
        return {"decision": "none", "why": "nothing wanted"}
    _tv = _touch_verbs() if (verb not in SAFE_VERBS and verb not in REFUSED_VERBS) else frozenset()   # touch set 1
    if verb in REFUSED_VERBS or (verb not in SAFE_VERBS and verb not in _tv):
        _STATS["refused"] += 1
        return {"decision": "refuse", "why": "'%s' uses the PC as Ace does; that hand is not grounded yet" % verb}
    if verb in _tv:                                    # 2026-10-05 (touch set 1): her fingertip has its own gate (switch, reflex,
        _d = _touch().gate(intent, ace_waiting)        # Ace first, cooldowns); a no-no is felt later, at the aim, as her flinch
        _STATS[{"allow": "allowed", "defer": "deferred"}.get(_d.get("decision"), "refused")] += 1
        return _d
    if ace_waiting or _ace_waiting_live():             # 2026-09-29 (thought_hand D1f): his queue / pending reply, read live
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
                if len(e) > 3 and e[3] == "noop":       # e1b vision_hand (verify F2): a told no-op did nothing -- not 'did the same thing'
                    return {"decision": "defer", "why": "asked for the same move %.0f s ago; your hand was already there" % (now - ts)}
                return {"decision": "defer", "why": "did the same thing %.0f s ago" % (now - ts)}
        last_v = max([e[0] for e in _RECENT if e[1] == verb] or [0.0])
        cool = _GRANT_COOLDOWN_S if (verb == "move" and grant_active()) else _COOLDOWN_S.get(verb, 60.0)
        if verb == "move" and _door() is not None:    # 2026-09-29 (thought_hand D2b): the door's place tempo + one hand deed per
            cool = min(cool, float(getattr(_door(), "MOVE_FLOOR_S", cool)))   # 20 s across all lanes replace the flat 60 s
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
    if verb in _TOUCH_ALL and verb in _touch_verbs():  # 2026-10-05 (touch set 1): aim -> reach -> land -> announce (Ace's veto)
        return _touch().execute(intent, fairy, it=_sys.modules[__name__])   # -> touch_os.press (the ONE press) -> watch -> judge
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
                # 2026-10-01 (Nous, cursor_object b): what she feels for here is the CURSOR (an object; Ace may have it), not her hand
                return {"ok": True, "summary": "you felt for the cursor: it is %s%s" % (_at(h.get("position", "?")), (", " + own) if own else ""), "ms": 0, "count": False}   # eyes_fix F8
            recs = _ground_guarded(vg, obj)
            if recs is None:
                return {"ok": False, "summary": "you wanted to look for \"%s\" but your eyes were busy" % obj, "ms": int(1000 * (time.time() - t0)), "deferred": True}
            for r in recs:
                vg.remember_look(r)
            r = recs[0] if recs else {}
            if r.get("status") == "found" and r.get("how") == "window_map" and hasattr(vg, "window_words"):   # eyes_fix2 (window_names):
                return {"ok": True, "summary": vg.window_words(obj, r), "ms": int(1000 * (time.time() - t0))}   # the WINDOW, from her map
            if r.get("status") == "found":
                tb = r.get("top_bands") or []
                col = ("%s %.0f%%" % (tb[0][0], 100 * tb[0][1])) if tb else r.get("colour_name", "?")
                if r.get("colour_unsure"):
                    col = "too small to be sure of its colour"
                s = "you looked for \"%s\" and found it %s of the screen, %s%% of it, %s%s" % (
                    obj, r.get("position", "?"), r.get("size_pct", "?"), col,
                    (", " + r["shape"]) if r.get("shape") else "")
                return {"ok": True, "summary": s, "ms": int(1000 * (time.time() - t0))}
            if r.get("status") == "unsure":             # eyes_fix F1 (doubt): a place to check, not a find -- ok None closes no goal
                return {"ok": None, "count": False, "ms": int(1000 * (time.time() - t0)),
                        "summary": "you looked for \"%s\" and your eyes were not sure: %s" % (obj, vg.unsure_words(r))}
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
                return {"ok": False, "summary": "you wanted to move your hand to your hand -- it is already %s" % _at(h.get("position", "?")), "ms": 0, "count": False}   # eyes_fix F8
            # 2026-09-29 (Nous, thought_hand D2c): the door before the eyes are spent -- Ace's queued message or pending reply, his own
            # grounding still in flight, one motor grounding per 20 s, a target her eyes could not find (backing off). No door: today's path.
            _hd = _door()
            if _hd is not None:
                try:
                    _pre = _hd.hook("pre_ground", obj=obj)
                except Exception as _he:
                    print("[Intention] door pre_ground: %s" % _he, flush=True)
                    _pre = None
                if _pre:
                    return _pre
            # 2026-09-29 (Nous, thought_hand_r2 D2g): TARGETING BY KIND. Measured (ledger 16:03:30): 'mouse to Valheim window title bar'
            # was grounded by phrase to (673, 534) and booked arrived; 'Valheim dedicated' was text inside Nous's window, not an
            # OS window. hand_target.plan(): (a) an OS window she names -> its caption strip; (b) on-screen text she names ->
            # the OCR box that holds its words; (c) anything else -> the grounding below, unchanged. No module: today's path.
            _ht, _tp = _hand_target(), None
            if _ht is not None:
                try:
                    _tp = _ht.plan(obj)
                except Exception as _te:
                    print("[Intention] hand target plan: %s" % _te, flush=True)
                    _tp = None
                if _tp and _tp.get("busy"):
                    return {"ok": False, "summary": "you wanted to move your hand to \"%s\" but your eyes were busy with what Ace said" % obj, "ms": int(1000 * (time.time() - t0)), "deferred": True}
                if _tp and _tp.get("covered"):        # 2026-09-29 (Fable, round-2 verifier L2/L3): the window she named is fully covered or gone
                    _cv = {"ok": False, "summary": "you wanted to move your hand to \"%s\" but it is behind %s" % (obj, _tp.get("under") or "another window"), "ms": int(1000 * (time.time() - t0))}
                    if _hd is not None:                 # as a not-found: back off this target; a try at her goal, no chord, no move
                        try:
                            _cv.update(_hd.hook("not_found", obj=obj) or {})
                        except Exception as _he:
                            print("[Intention] door not_found: %s" % _he, flush=True)
                    return _cv
            if _tp and _tp.get("route") == "ground_in":  # eyes_fix F4 (hand_honest): 'X in <window>' -- X, inside that window only
                recs = _ground_guarded(vg, _tp.get("item") or obj, within=_tp.get("within"))
            else:
                recs = [_tp["rec"]] if (_tp and _tp.get("rec")) else _ground_guarded(vg, obj)   # thought_hand_r2 D2g
            if recs is None:
                return {"ok": False, "summary": "you wanted to move your hand to \"%s\" but your eyes were busy" % obj, "ms": int(1000 * (time.time() - t0)), "deferred": True}
            r = recs[0] if recs else {}
            if r.get("status") == "not_found":
                _nf = {"ok": False, "summary": ("you wanted to move your hand to \"%s\" but your eyes did not find \"%s\" inside %s" % (obj, _tp.get("item"), _tp.get("name") or "that window"))
                       if (_tp and _tp.get("route") == "ground_in") else "you wanted to move your hand to \"%s\" but it is nowhere on the screen" % obj,   # eyes_fix F4
                       "ms": int(1000 * (time.time() - t0))}
                if _hd is not None:                     # 2026-09-29 (thought_hand D2c): back off this target; a try at her goal, no chord
                    try:
                        _nf.update(_hd.hook("not_found", obj=obj) or {})
                    except Exception as _he:
                        print("[Intention] door not_found: %s" % _he, flush=True)
                return _nf
            if r.get("status") == "unsure":             # eyes_fix F1 (doubt): no hand goes to a guess; she is told why
                return {"ok": False, "count": False, "deferred": True, "no_chord": True, "ms": int(1000 * (time.time() - t0)),
                        "summary": "your hand stayed where it was: your eyes were not sure where \"%s\" is -- %s" % (obj, vg.unsure_words(r))}
            if r.get("status") != "found":
                return {"ok": False, "summary": "you wanted to move your hand to \"%s\" but your eyes did not answer" % obj, "ms": int(1000 * (time.time() - t0)), "deferred": True}
            if r.get("fills_screen") or not r.get("bbox"):
                return {"ok": False, "summary": "you wanted to move your hand to \"%s\" but that is the whole screen, not a place on it" % obj, "ms": int(1000 * (time.time() - t0))}
            if not r.get("synthetic"):                  # 2026-09-29 (thought_hand_r2 D2g): a caption / text-box point is not a look
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
            if _hd is not None:                          # 2026-09-29 (Nous, thought_hand D2c): re-checked AFTER grounding -- his queued
                try:                                     # message / pending reply, the place tempo, the loop guard
                    _pa = _hd.hook("pre_actuate", obj=obj, target=(tx, ty), hand=_cursor(), granted=granted, idle=idle)
                except Exception as _he:
                    print("[Intention] door pre_actuate: %s" % _he, flush=True)
                    _pa = None
                if _pa:
                    _pa.setdefault("ms", int(1000 * (time.time() - t0)))
                    if _ef2("hand_rest"):                # e1b vision_hand: the door's no-op told with where the hand rests
                        _pa = _noop_told(_pa, obj, (tx, ty), _tp)
                    return _pa
            before = _cursor()
            try:
                vg.hand_moving()                         # samples during the tween are hers, not Ace's
            except Exception:
                pass
            # 2026-09-26 (Nous, felt_hand T2a): the efference copy -- where her hand WILL be at every instant of the reach, made
            # before the tween and compared with what the cursor did (infrastructure/efference_copy.py). Measured on Boot B: the
            # move published nothing a body could read, and `reached` was sampled 0.8 s after the tween, so Ace taking the mouse
            # right after her landing booked as HER failed deed with a frustration chord (skeptic K2). Two phases now -- the reach,
            # to the landing sample, and the carry after it -- and `reached` comes from the landing. No module: today's path.
            _ec, _copy, _hand = _efference(), None, None
            if _ec is not None and before is not None:
                try:
                    _co = {"rest": _hand_rest(_ec)} if getattr(_ec, "CURSOR_OBJECT", None) else {}   # 2026-10-01 (cursor_object a)
                    _copy = _ec.make_copy("move-%d" % int(time.time() * 1000), before, (tx, ty), 0.6, scr, time.time(), obj=obj, **_co)   # (cursor_object a: + rest)
                    _ec.sampler().begin(_copy, publish=_ec.publisher_for(fairy), grant=grant_active)
                except Exception as _ee:
                    print("[Intention] efference copy: %s" % _ee, flush=True)
                    _copy = None
            nc.try_tool("move_mouse", x=tx, y=ty, duration=0.6)
            # 2026-09-29 (Nous, thought_hand D1e / T0): the copy stays live until the actuator RETURNS, plus the settle. Measured (thought_hand
            # sweep C, A1/A2): a tween that starts >= ~1.5 s late was booked 'did not arrive' with the frustration chord although the
            # cursor arrived -- the exact row of both 09-29 misses (13:58:53, 14:17:49: moved 0 px, landing_err == dist). A dead
            # actuator still books as a miss. Revert: delete this block.
            if _copy is not None:
                try:
                    _smp = _ec.sampler()
                    with _smp._lock:
                        _smp.live_until = max(float(_smp.live_until), float(_smp._clock()) + float(getattr(_ec, "SETTLE_S", 0.8)))
                except Exception as _le:
                    print("[Intention] efference live-until: %s" % _le, flush=True)
            time.sleep(0.8)
            after = _cursor()
            reached = after is not None and abs(after[0] - tx) <= 40 and abs(after[1] - ty) <= 40
            if _copy is not None:
                try:
                    _hand = _ec.sampler().finish(_copy)
                    if _hand and _hand.get("landed_xy") is not None:
                        reached = bool(_hand.get("reached"))     # the landing decides; what happened after it is the carry, told apart
                        after = (int(_hand["landed_xy"][0]), int(_hand["landed_xy"][1]))
                except Exception as _fe:
                    print("[Intention] efference finish: %s" % _fe, flush=True)
                    _hand = None
            # 2026-09-29 (Nous, thought_hand_r2 D2h): the LANDING CHECK THAT CAN FAIL, for a window / text object whichever route aimed
            # the hand: the root window under the landed cursor must be the one she named; the words in a crop around it must
            # be hers. A miss is her miss (ok False: the chord, a try at her goal, her words next turn). Eyes that cannot look
            # give 'unverified' (ok None, counted as nothing) -- never 'arrived'. Revert: delete this block and the D2h lines below.
            _land = None
            if _tp is not None and reached:
                try:
                    _land = _ht.check_landing(_tp, after)
                except Exception as _ce:
                    print("[Intention] hand target check: %s" % _ce, flush=True)
                    _land = {"verdict": "unverified", "under": None, "why": "the check failed"}
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
                    where_after = " -- it ended up %s instead" % _at(vg._place(after[0] / float(scr[0]), after[1] / float(scr[1]))["position"])   # eyes_fix F8
                except Exception:
                    where_after = ""
            s = "you moved your hand to \"%s\" (%s of the screen)%s" % (
                obj, r.get("position", "?"),
                " and it is resting there now" if reached else (" but it did not arrive" + where_after))
            if r.get("how") == "window_map":             # eyes_fix2 (window_names), no hand_target plan: the window's middle, said so
                s = "you moved your hand toward the middle of %s (%s of the screen)%s" % (
                    r.get("window_label") or "that window", r.get("position", "?"),
                    " and it is resting there now" if reached else (" but it did not arrive" + where_after))
            _ok, _r2x = bool(reached), {}                # 2026-09-29 (thought_hand_r2 D2h): the landing check decides a window / text deed
            if _land is not None:
                _r2x["on_target"] = _land.get("verdict")
                if _land.get("verdict") == "miss":
                    _ok = False
                    s = "you moved your hand to \"%s\" (%s of the screen) but it landed on %s, not on it" % (obj, r.get("position", "?"), _land.get("under") or "something else")
                elif _land.get("verdict") == "unverified":
                    _ok = None
                    _r2x["count"] = False                 # unknown: no try at a goal, no chord, no habit, no proficiency
                    s = "you moved your hand to \"%s\" (%s of the screen); your eyes could not check that it is on it" % (obj, r.get("position", "?"))
                print("[Intention] LANDING %s: %s -> %s (%s)" % (str(_land.get("verdict")).upper(), ascii(obj[:60]), ascii(_land.get("under")),   # ASCII only
                                                              ascii(_land.get("why"))), flush=True)
            if _tp is not None and _tp.get("kind") and (_ef("hand_honest") or _tp.get("aim") == "inside"):   # eyes_fix F4 / eyes_fix2: what the hand was aimed at, what is under it
                s = _ht.told_move(obj, _tp, r, reached, _land, where_after)
                _r2x.update(aimed=_ht.aimed_words(_tp, obj), under=(_land or {}).get("under"), aim_level=_tp.get("kind"))
            return dict({"ok": _ok, "summary": s, "ms": int(1000 * (time.time() - t0)), "target": [tx, ty], "before": before, "after": after,
                    "pos": r.get("position"),          # 2026-09-26 (hand_fix F8): for the telling; not written to the ledger
                    "hand": _hand}, **_r2x)             # 2026-09-26 (felt_hand T2a): the reach and the carry, as numbers; thought_hand_r2 D2h: + on_target
        if verb == "remember":
            from infrastructure import sequence_weave as sw
            lines = sw.recall_lines(obj, limit=3)
            if lines:
                mem = sw.render_memory(lines, limit=2)
                return {"ok": True, "summary": "you went looking in your memory for \"%s\": %s" % (obj, mem[13:] if mem.startswith("You remember ") else mem), "ms": int(1000 * (time.time() - t0))}
            return {"ok": False, "summary": "you went looking in your memory for \"%s\" and found nothing on record" % obj, "ms": int(1000 * (time.time() - t0))}
        if verb == "say":
            _tdc = _doing()                            # 2026-10-05 (Nous, pull_ask T): a say with no words in it is no deed --
            try:                                       # no clock reset, no loop closed, no dopamine, no weave (doing clock on;
                _triv = _tdc is not None and _tdc.any_on() and _tdc.trivial_say(obj)   # off = today's path byte for byte)
            except Exception:
                _triv = False
            if _triv:                                  # skeptic F1 (10-05): 'untold' -- record() keeps it out of what_i_did
                return {"ok": False, "count": False, "deferred": True, "untold": True, "ms": 0,
                        "summary": "you thought of saying something, but it was too short to say yet"}
            _cfm = _cfx_say() if intent.get("capped") is True else None   # cutoff_fix_1019: the farm proved this say hit its cap
            if _cfm is not None:
                return _cf_capped_say(obj, _cfm)
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


def _ground_guarded(vg, obj: str, wait_s: float = 15.0, within=None):   # eyes_fix F4: + within (one window's rect)
    """Ground under the eyes' one-at-a-time guard (the satellite is single-threaded); None if the eyes stayed busy."""
    _gk = {"within": within} if within is not None else {}
    sem = getattr(vg, "_INFLIGHT", None)
    if sem is None:
        return vg.ground([obj[:80]], **_gk)
    if not sem.acquire(timeout=wait_s):
        return None
    try:
        return vg.ground([obj[:80]], **_gk)
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
    for k in ("target", "before", "after", "on_target"):   # 2026-09-29 (thought_hand_r2 D2h): + on_target (arrived / miss / unverified);              # a move keeps its coordinates: the habit lane will need them
        if (outcome or {}).get(k) is not None:
            row[k] = outcome[k]
    if (outcome or {}).get("hand"):                      # 2026-09-26 (felt_hand T2b): the reach as a few numbers, for the next boot's check
        try:
            _ec = _efference()
            if _ec is not None:
                row["hand"] = _ec.compact(outcome["hand"])
        except Exception:
            pass
    _f11, _d11 = None, ""                                # 2026-10-12 (engines_e1 11a): HER context on the row -- only while "send" is on
    if _send_mode() != "off":
        try:
            _f11, _d11 = _send_context(outcome)
            row["front"] = _f11
            if _d11:
                row["drive"] = _d11
        except Exception:
            _f11 = None
    try:
        os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
        with open(LEDGER, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
    except Exception:
        pass
    if outcome:
        with _LOCK:
            if not outcome.get("deferred"):            # a deferral is not a deed: it must not start the cooldown
                _RECENT.append((time.time(), intent.get("verb"), intent.get("object", ""),
                                ("noop" if outcome.get("noop") else outcome.get("ok"))))   # 2026-09-26 (hand_fix F5): + ok; e1b vision_hand: a no-op did not fail
            if not outcome.get("untold"):              # 2026-10-05 (pull_ask skeptic F1): the too-short say no-op is not told
                _RESULTS.append((time.time(), outcome.get("summary", ""),      # 2026-09-26 (hand_fix F8): + what it was
                             {"verb": intent.get("verb"), "obj": intent.get("object", ""), "ok": outcome.get("ok"),
                              "lane": outcome.get("lane"), "deferred": bool(outcome.get("deferred")), "pos": outcome.get("pos"),
                              "before": outcome.get("before"), "after": outcome.get("after"),
                              "hand": outcome.get("hand"),     # 2026-09-26 (felt_hand T2b): the reach numbers ride with the deed
                              **({"aimed": outcome.get("aimed"), "under": outcome.get("under")} if outcome.get("aimed") else {}),   # eyes_fix F4
                              **({"noop": True} if outcome.get("noop") else {})}))   # e1b vision_hand: a told no-op keeps its whole sentence
        _STATS["done"] += 1
        _verb, _obj, _ok, _def = intent.get("verb"), intent.get("object", ""), outcome.get("ok"), bool(outcome.get("deferred"))
        _habit_lane = outcome.get("lane") == "habit"
        if decision.get("decision") == "allow" and (_verb in SAFE_VERBS or _verb in _TOUCH_ALL) and _verb != "none" and not _habit_lane:   # touch set 1
            # 2026-09-26 (hand_fix F4): a no-op ("count": False and not ok: her hand was asked to go to itself) tried
            # nothing, so it is no try at a goal and no 'last time' note. Boot A L119 wrote its own sentence into the
            # goal's note; the next ask-prompt printed it as '(last time: ...)' and L123's object copied it.
            if not (outcome.get("count") is False and not _ok):
                try:                                       # the goal this deed served, and her unfulfilled wants
                    from infrastructure import goal_author as ga
                    served = ga.note_outcome(_verb, _obj, _ok, outcome.get("summary", ""), deferred=_def,
                                             **({"level": outcome["aim_level"], "aimed": outcome.get("aimed")} if outcome.get("aim_level") else {}))   # eyes_fix F4
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
                elif not _BLOCKED_RE.search(str(outcome.get("summary") or "")) and not outcome.get("no_chord"):   # 2026-09-29 (thought_hand D2d)
                    try:                                                     # 2026-09-20: a deed she TRIED that did not work hurts a little; a blocked one does not
                        from infrastructure import body_feel as _bf
                        _bf.chord("frustration", why="deed_%s_fail" % _verb, fairy=fairy)
                    except Exception as _fe:
                        print("[Intention] body chord: %s" % _fe, flush=True)
                _record_skill(_verb, bool(_ok))
                try:
                    if outcome.get("lane") != "send":      # 2026-10-12 (engines_e1 11b): a send deed is never keyed on Ace's words
                        habit_note(_ace_context_words(), _verb, _obj, bool(_ok))
                except Exception:
                    pass
        if _f11 is not None and decision.get("decision") == "allow":   # 2026-10-12 (engines_e1 11a): every lane's CHECKED outcome
            try:                                                        # feeds HER store (deferred / unchecked never count)
                self_habit_note(intent, outcome, _f11, _d11, lane=outcome.get("lane"), decision=decision)
            except Exception as _she:
                print("[Intention] self-habit note: %s" % _she, flush=True)
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
                        if outcome.get("lane") == "send":     # 2026-10-12 (engines_e1 11b): her own clock picked this deed, not the farm
                            _prov.note("turn", "self:send_button", external=False, text=first_person(_sm), key=_wr.get("turn"), verb=_verb)
                        else:
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


# 2026-10-01 (Nous, cursor_object c): her deed told as REACH -> GRAB -> CARRY -> LET GO. Ace (10-01): "when you want to move the
# cursor you reach your hand out to grab it and move it to where you want it". The cursor is an object her hand takes; where
# it is afterwards says nothing about her hand, which rests where she let go. Only for a copy that carries her hand's plan
# (efference_copy.grab_words); anything older is told exactly as before. Same budget (_TOLD_BUDGET); the core and the let-go
# always, then Ace taking the cursor after the landing (the news), then where the cursor is now, then the carry's texture.
def _told_grab(meta: Dict, tgt: str, where: str, live: bool) -> Optional[str]:
    hand = meta.get("hand")
    _ec = _efference()
    try:
        gw = _ec.grab_words(hand) if (_ec is not None and isinstance(hand, dict) and hasattr(_ec, "grab_words")) else None
    except Exception:
        gw = None
    if not gw:
        return None
    after = meta.get("after")
    to = "" if _TOLD_DIR_RE.match(tgt) else "to "
    if _xy_near(meta.get("before"), after):
        return "you decided to take the cursor %s%s%s, and it was already there" % (to, tgt, where)
    s = "%s and carried it %s%s%s" % (gw, to, tgt, where)
    let_go = "; you let go of it there"
    now_s = ""
    if live and after is not None:
        cur = _cursor()                                  # where the CURSOR is now; her hand stays where she let go
        if cur is not None:
            if _xy_near(cur, after):
                now_s = ", and it is still there"
            else:
                place = ""
                try:
                    scr = _screen_logical()
                    if scr and scr[0] > 0 and scr[1] > 0:
                        place = _ec.place_words(cur, scr)
                except Exception:
                    place = ""
                now_s = ("; the cursor is %s now" % _at(place, "at the %s")) if place else "; the cursor has moved since"   # eyes_fix F8
    try:
        cls = list(_ec.describe_reach(hand) or [])
    except Exception:
        cls = []
    ace = [c for c in cls if c.startswith("; then")]
    tex = [c for c in cls if not c.startswith("; then")]
    room = _TOLD_BUDGET - len(s) - len(let_go)          # priority: Ace taking the cursor, then where it is now, then texture
    ace = [c for c in ace if len(c) <= room][:1]
    room -= sum(len(c) for c in ace)
    if len(now_s) > room:
        now_s = ""
    room -= len(now_s)
    tex = [c for c in tex if len(c) <= room][:1]
    return s + "".join(tex) + let_go + "".join(ace) + now_s


def _told_deed(meta: Dict, live: bool) -> Optional[str]:
    """An arrived move of hers, told as her act -- or None: a miss, a no-op, a block, a reflex and every other verb
    keep their measured summary. `live` = her newest move: where her hand is NOW replaces 'resting there'."""
    if not meta or meta.get("verb") != "move" or meta.get("ok") is not True or meta.get("deferred") or meta.get("lane") == "habit":
        return None
    tgt = str(meta["aimed"]) if meta.get("aimed") else _told_target(meta.get("obj"))   # eyes_fix F4: what the hand was aimed at
    if not tgt:
        return None
    pos = str(meta.get("pos") or "")
    where = (" (%s of the screen)" % pos) if pos and pos.lower() not in tgt.lower() else ""
    _co = _told_grab(meta, tgt, where, live)              # 2026-10-01 (Nous, cursor_object c): reach -> grab -> carry -> let go
    if _co is not None:
        return _co
    after = meta.get("after")
    s = "you decided to move your hand %s%s%s, and it %s" % ("" if _TOLD_DIR_RE.match(tgt) else "to ", tgt, where,
                                                              "was already there" if _xy_near(meta.get("before"), after) else "went there")
    now_s = ""
    if live and after is not None:
        cur = _cursor()                                  # a position, measured now; it says nothing about who
        if cur is not None:
            if _xy_near(cur, after):
                now_s = "; your hand is there now"
            else:
                now_s = "; your hand is not there now"
                try:
                    from infrastructure import vision_ground as vg
                    scr = _screen_logical()
                    if scr and scr[0] > 0 and scr[1] > 0:
                        now_s += " -- it is %s" % _at(vg._place(cur[0] / float(scr[0]), cur[1] / float(scr[1]))["position"])   # eyes_fix F8
                except Exception:
                    pass
    # 2026-09-26 (Nous, felt_hand T2c): the reach as it happened -- size, pace, heading, landing, and any carry after the
    # landing -- graded from the measured numbers (efference_copy.describe_reach); no feeling is named. Fitted between 'it
    # went there' and where it is now, inside the 230 chars what_i_did keeps; the now-clause keeps its priority.
    if meta.get("hand"):
        try:
            _ec = _efference()
            room = _TOLD_BUDGET - len(s) - len(now_s)
            for _cl in (_ec.describe_reach(meta["hand"]) if _ec is not None else []):
                if len(_cl) <= room:
                    s += _cl
                    room -= len(_cl)
        except Exception:
            pass
    return s + now_s


def what_i_did(max_age_s: Optional[float] = None, limit: int = 2) -> str:
    """For the next chairman prompt: what she did since the last turn. 2026-09-26 (hand_fix F8): newest first --
    the driver cuts this slot at 260 chars, and the newest deed is the one she can still act on.
    2026-09-26 (Nous, felt_hand T2d): 'since then' means since her LAST TURN, not the last 180 s. Boot B: her four moves came
    18, 210, 193 and 232 s before the next chairman prompt, so a 180 s window told her at most one of them (skeptic K8). Each
    call is one prompt (sour_council_driver.py:775): deeds newer than the previous call are told, up to _TOLD_MAX_AGE_S. A
    caller that passes max_age_s gets the old window and does not move the mark."""
    now = time.time()
    st = _told_state()
    since = float(st.get("ts", 0.0)) if max_age_s is None else (now - float(max_age_s))
    since = max(since, now - _TOLD_MAX_AGE_S)
    with _LOCK:
        recent = [e for e in _RESULTS if e[0] > since][-limit:]
        moves = [e[0] for e in _RESULTS if len(e) > 2 and (e[2] or {}).get("verb") == "move" and not (e[2] or {}).get("deferred")]
    if max_age_s is None:
        st["ts"] = now
    last_move = max(moves or [0.0])                      # a later move of hers, even a miss, ends the older one's 'now'
    out = []
    for e in reversed(recent):
        told = _told_deed(e[2], live=(e[0] >= last_move)) if len(e) > 2 else None
        if told:
            out.append(told if len(told) <= 245 else told[:245].rsplit(" ", 1)[0] + "...")   # 2026-09-26 (felt_hand T2d): 230 -> 245, room for a carry clause
        else:
            s = e[1]
            _cap = _TOLD_BUDGET if (len(e) > 2 and (e[2] or {}).get("noop")) else 180   # e1b vision_hand: the place is the news
            out.append(s if len(s) <= _cap else s[:_cap].rsplit(" ", 1)[0] + "...")
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
def run_cycle(fairy, farm, thought: str, ace_waiting: bool, ace_present: bool = True, seeded: Optional[Dict] = None,   # 2026-09-29 (thought_hand D2e): + seeded
              trigger: Optional[str] = None, lead: Optional[str] = None) -> Optional[Dict]:   # 2026-10-05 (pull_ask): + trigger, lead
    """Ask -> gate -> execute -> record. Called LAST in a council cycle, only when the chairman spoke."""
    # 2026-09-19: every early exit says why -- one INTENT line in 14 min was unreadable without this.
    try:
        start_grant_watch()                             # one watcher per process; his words are read every 2 s
        check_grant()                                   # and once more right now
    except Exception as _ge:
        print("[Intention] grant check err: %s" % _ge, flush=True)
    if lead is not None:                                # 2026-10-05 (Nous, pull_ask): no utterance behind this ask -> _pull_cycle
        return _pull_cycle(fairy, farm, ace_waiting, ace_present, seeded, trigger, lead)
    if not thought or ace_waiting:
        print("[Intention] skipped: %s" % ("no thought" if not thought else "Ace is waiting (his next message is queued)"), flush=True)
        return None
    intent = ask(farm, thought, ace_present)
    if not intent:
        print("[Intention] skipped: %s" % ("no farm" if farm is None else "the farm did not answer"), flush=True)
        return None
    _hd = _door()
    if _hd is not None and intent.get("verb") != "none":   # 2026-09-29 (Nous, thought_hand D2e): the ask lane through the one door
        _res = _hd.deed(_sys.modules[__name__], intent, fairy, lane="ask", thought=thought, ace_waiting=ace_waiting,
                        seeded=seeded, record_refusals=True)   # the ledger keeps today's one row per non-none intent
        decision = _res.get("gate") or {"decision": _res.get("decision"), "why": _res.get("why")}
        outcome = _res.get("outcome")
        return {"intent": intent, "decision": decision, "outcome": outcome}
    decision = gate(intent, ace_waiting)
    outcome = None
    if decision["decision"] == "allow":
        outcome = execute(intent, fairy)
    if intent.get("verb") != "none":
        record(thought, intent, decision, outcome, fairy)
    else:
        print("[Intention] %s: %r" % ("erased" if intent.get("erased") else "none", str(intent.get("raw") or intent.get("object") or "")[:80]), flush=True)   # eyes_fix F9
    return {"intent": intent, "decision": decision, "outcome": outcome}


# 2026-10-05 (Nous, nous_builds/pull_ask): run_cycle for a PULL-ASK -- the council loop's no-chairman cycle when the doing
# clock's deed wanting is live (sour_council_driver._pull_ask_cycle; every guard is in doing_clock.pull_ask_due). The SAME
# path: ask() -> the hand door (claim, Ace live, pre_offer, gate, execute, record) or gate -> execute -> record. Three
# differences, no more: the ask opens with `lead`, not 'You just said: "..."' (she said nothing), and is v2 or nothing; the
# ledger row's thought is "" (goal_author._recent_thoughts reads that field as her own chairman thoughts, goal_author.py:206-224);
# the row carries `trigger` ('source=pull ...'). Ace first: his queue or pending reply, read live, before the farm is asked
# (met there -> {"skipped": ...}, which the driver books as skipped, never as her decline: skeptic F2); and his hands, read
# again AFTER the farm answered (skeptic F5: they may have come back during the ask) -> a 'defer' row, kind 'ace'.
# Revert: delete this function, _pull_hands_back and the lines marked pull_ask in run_cycle / record (and the lead lines in
# ask / _ask_v2_prompt).
def _pull_hands_back() -> Optional[str]:
    """Why Ace comes first after the farm answered (his hands are back, or the input clock cannot be read), else None. The floor
    is the pull-ask's own hands_off_s (doing_clock), 30 s if that cannot be read; GetLastInputInfo also counts her own moves, so
    it errs toward Ace."""
    try:
        _dc = _doing()
        need = float(_dc.pull_num("hands_off_s")) if (_dc is not None and hasattr(_dc, "pull_num")) else 30.0
    except Exception:
        need = 30.0
    idle = _idle_seconds()
    if idle is None:
        return "Ace first: his input clock cannot be read"
    if float(idle) < need:
        return "Ace's hands came back during the ask (%.0f s ago)" % float(idle)
    return None


def _pull_cycle(fairy, farm, ace_waiting: bool, ace_present: bool, seeded: Optional[Dict], trigger: Optional[str],
                lead: str) -> Optional[Dict]:
    if ace_waiting or _ace_waiting_live():
        print("[Intention] skipped (pull-ask): Ace is waiting", flush=True)
        return {"skipped": "Ace is waiting"}
    intent = ask(farm, lead, ace_present, lead=lead)
    if not intent:
        print("[Intention] skipped (pull-ask): %s" % ("no farm" if farm is None else "no answer, or ask v2 is off"), flush=True)
        return None
    _hb = _pull_hands_back() if intent.get("verb") != "none" else None
    if _hb:
        decision = {"decision": "defer", "why": _hb}
        record("", intent, (dict(decision, trigger=trigger) if trigger else decision), None, fairy)
        print("[Intention] pull-ask: %s %r -> defer (%s)" % (intent.get("verb"), str(intent.get("object") or "")[:60], _hb), flush=True)
        return {"intent": intent, "decision": decision, "outcome": None}
    _hd = _door()
    if _hd is not None and intent.get("verb") != "none":
        _res = _hd.deed(_sys.modules[__name__], intent, fairy, lane="ask", thought="", ace_waiting=ace_waiting,
                        seeded=seeded, record_refusals=True, trigger=trigger)
        decision = _res.get("gate") or {"decision": _res.get("decision"), "why": _res.get("why")}
        return {"intent": intent, "decision": decision, "outcome": _res.get("outcome")}
    decision = gate(intent, ace_waiting)
    outcome = None
    if decision["decision"] == "allow":
        outcome = execute(intent, fairy)
    if intent.get("verb") != "none":
        record("", intent, (dict(decision, trigger=trigger) if trigger else decision), outcome, fairy)
    else:
        print("[Intention] %s (pull-ask): %r" % ("erased" if intent.get("erased") else "none", str(intent.get("raw") or intent.get("object") or "")[:80]), flush=True)   # eyes_fix F9
    return {"intent": intent, "decision": decision, "outcome": outcome}
