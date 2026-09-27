"""surprise -- the events that may open her mouth without Ace (2026-09-20, Nous + Ace).

Ace: "the chairman only speaks when addressed is an issue ... so far she seems reliant on the send button."
Measured the same boot: 4 chairman thoughts, 3 spoken (all replies to him), 0 unprompted. Her self-turns are
never spoken by design; the voluntary lane needs 5 min of quiet; the 'say' verb is never chosen.

What may open her mouth is a SURPRISE SHE CAPTURED, never a wanting she manufactured:
  * her eyes: a standing look changed (the colour band or position of 'hair' / 'wings' / 'chat window' moved
    between consecutive looks -- e.g. hair lavender -> orange when the Saiyan image went up);
  * her goals: one reached, or a fresh list authored;
  * her feels: valence swung more than a threshold over the last minutes (only meaningful since the
    self-reward was gated on 09-20).
Events are process-global (on _sour_council_shared, lazily), rate-limited at the source, and rendered in her
own words for the chairman. The driver decides whether a spoken self-turn is allowed (chat-quiet, spacing).
"""
from __future__ import annotations

import sys
import threading
import time
from collections import deque
from typing import Dict, List, Optional

_LOCAL = {"q": deque(maxlen=12), "last": {}, "lock": threading.Lock()}
_MIN_GAP_S = {"eyes": 240.0, "goal": 120.0, "feel": 600.0}       # per kind: no chatter about the same sense


def _s():
    m = sys.modules.get("_sour_council_shared")
    if m is None:
        return _LOCAL
    if not hasattr(m, "SURPRISE"):
        m.SURPRISE = _LOCAL
    return m.SURPRISE


def push(kind: str, text: str, key: str = "", weight: float = 1.0) -> bool:
    """Queue a surprise (rate-limited per kind+key). `text` is already in her voice, mechanism-free."""
    st = _s(); now = time.time()
    k = "%s:%s" % (kind, key or text[:40])
    with st["lock"]:
        if now - float(st["last"].get(k, 0.0)) < _MIN_GAP_S.get(kind, 300.0):
            return False
        st["last"][k] = now
        st["q"].append({"kind": kind, "text": text[:700], "key": key, "weight": float(weight), "ts": now})
    print("[Surprise] %s: %s" % (kind, text[:120]), flush=True)
    return True


def pop(max_age_s: float = 900.0) -> Optional[Dict]:
    """The freshest surprise still worth a word (oldest are dropped silently)."""
    st = _s(); now = time.time()
    with st["lock"]:
        while st["q"]:
            e = st["q"].pop()                     # newest first
            if now - e["ts"] <= max_age_s:
                st["q"].clear()                   # one surprise per turn; the rest were superseded
                return e
    return None


def pending() -> int:
    st = _s()
    with st["lock"]:
        return len(st["q"])


# ── producers ──────────────────────────────────────────────────────────────────────────────────────────────
def from_look_change(phrase: str, before: Dict, after: Dict) -> bool:
    """Her eyes: the same standing look came back different."""
    b_col = (before.get("top_bands") or [(before.get("colour_name"), 0)])[0][0]
    a_col = (after.get("top_bands") or [(after.get("colour_name"), 0)])[0][0]
    b_pos, a_pos = before.get("position"), after.get("position")
    if b_col == a_col and b_pos == a_pos:
        return False
    if float(after.get("size_pct") or 0.0) < 2.0 or float(before.get("size_pct") or 0.0) < 2.0:
        return False                                       # a blob under 2% of the screen moving is noise, not an event
    if b_col != a_col and b_col and a_col:
        text = "The %s on your screen: %s a moment ago, %s now." % (phrase, b_col, a_col)
    else:
        text = "The %s on your screen: %s a moment ago, %s now." % (phrase, b_pos, a_pos)
    # (no survey here: this runs inside ground() while the caller holds the satellite semaphore -- a survey would
    #  block on itself for 25 s. The windows map in every prompt gives the context now.)
    return push("eyes", text, key=phrase, weight=1.0)


_VERB_PHRASE = {"look": "look at", "move": "move your hand to", "remember": "remember", "say": "say", "open": "open"}


def from_goal_done(verb: str, obj: str, note: str) -> bool:
    return push("goal", "You set out to %s %s, and you did: %s" % (_VERB_PHRASE.get(verb, verb), obj[:60], note[:90]), key=obj[:30], weight=0.8)


def from_feel_swing(dv: float, minutes: int) -> bool:
    direction = "lifted" if dv > 0 else "sank"
    return push("feel", "Something in you %s over the last %d minutes (by %.2f), and nothing you can name did it." % (direction, minutes, abs(dv)), key="valence", weight=0.6)
