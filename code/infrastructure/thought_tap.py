"""thought_tap -- her own words move her hand: the chairman lane only (T-chair). 2026-09-29 (Nous, thought_hand D2).

Ace, 2026-09-29: "if she is actively thinking about moving the mouse her autopilot system should be responding. she only seems
to be able to move a little bit". Measured (Boot C, 12 min): 10 of her thoughts spoke of moving her hand; 2 INTENT decisions;
1 move. Every move came from intention.ask(), a second Qwen call that re-derives 'verb: object' from what she just said -- and
the named place survived that re-derivation 2 times in 8 (sweep B eval_result.json ask_summary.all).

What this does, after the chairman has spoken (sour_council_driver, after the report-back, before the INTENTION block):
  1. reads the chairman's OWN words (_thought, never the seat-verdict fallback) with the v2 reader
     (infrastructure/volition_read.py): a present WANT of hers, with a place her eyes can look for; vetoed clauses (negation,
     past, modal, reported, instruction, disclaimed) and echoes of the prompt's non-her slots (the told deeds, the goal list,
     the eyes percept) never act. Her first-person agreement with Ace is hers and does act.
  2. offers it through the hand door (infrastructure/hand_door.py) as lane 'reader': one claim, Ace first (live), tempo,
     budget, backoff, loop guard; then intention.gate / execute / record exactly as the ask lane does.
  3. returns {'acted': True} when the door ALLOWED a deed this turn -- the driver then skips the ask (the second Qwen call) for
     this turn only. On every other turn the ask runs as today.
Not tapped in v1 (they wait until the chairman lane's live false-positive rate is measured): chain thoughts (T-chain), the
voluntary template sentences (T-voluntary), held wants, the autopilot 'act' lane.
Revert: delete this file (the driver's tap then does nothing), or set AKASHIC_THOUGHT_HAND=0 in her environment.
"""
from __future__ import annotations

import threading
import time
from typing import Dict, Optional

_STATS = {"turns": 0, "wants": 0, "acted": 0, "deferred": 0, "no_want": 0, "no_place": 0, "vetoed": {}, "dropped": 0,
          "told_echo_drops": 0, "errors": 0}
_LOCK = threading.Lock()


def stats() -> Dict:
    with _LOCK:
        s = dict(_STATS)
        s["vetoed"] = dict(_STATS["vetoed"])
    return s


def _say(msg: str) -> None:
    """A diagnostic must never be the failure: ASCII only (her console has been cp1252), and a print that raises is swallowed."""
    try:
        print(str(msg).encode("ascii", "replace").decode("ascii"), flush=True)
    except Exception:
        pass


def _bump(k: str, n: int = 1) -> None:
    with _LOCK:
        _STATS[k] = _STATS.get(k, 0) + n


def _touch_blocks(clause) -> bool:
    """2026-10-05 (touch set 1): touch.reader_blocks -- False when touch is absent or its switch is off (today's path)."""
    try:
        from infrastructure import touch as _t
    except Exception:
        return False
    try:
        return bool(_t.reader_blocks(clause))
    except Exception:
        return False


def offer(fairy, thought: str, mode: str = "self", told: str = "", goals: str = "", percept: str = "",
          seeded: Optional[Dict] = None) -> Dict:
    """One chairman turn. Returns {'acted', 'read', 'deed'}; never raises."""
    try:
        from infrastructure import volition_read as vr
        from infrastructure import hand_door as door
        from infrastructure import intention as it
    except Exception as e:
        _bump("errors")
        _say("[ThoughtHand] unavailable: %s" % e)
        return {"acted": False, "read": None, "deed": None}
    _bump("turns")
    slots = {k: v for k, v in (("told", told), ("goals", goals), ("percept", percept)) if v}
    r = vr.read(thought, slots=slots, lane="chair")
    with _LOCK:
        for v, _c in r.get("vetoed") or []:
            _STATS["vetoed"][v] = _STATS["vetoed"].get(v, 0) + 1
        _STATS["dropped"] += len(r.get("dropped") or [])
        _STATS["told_echo_drops"] += sum(1 for w, _c in (r.get("dropped") or []) if "told" in w)
    if not r.get("act"):
        _bump("no_place" if r.get("target") is None and r.get("clause") else "no_want")
        if r.get("vetoed") or r.get("dropped") or r.get("clause"):
            _say("[ThoughtHand] reader (%s): no deed -- %s%s%s" % (
                mode, r.get("why", "")[:100],
                (" | vetoed %s" % [v for v, _c in r["vetoed"]]) if r.get("vetoed") else "",
                (" | dropped %s" % [w.split(" (")[0] for w, _c in r["dropped"]]) if r.get("dropped") else ""))
        return {"acted": False, "read": r, "deed": None}
    _bump("wants")
    if _touch_blocks(r.get("clause")):                 # 2026-10-05 (touch set 1, FS12.3, T14 a): while touch is on her own 'tap /
        _bump("touch_words")                           # press / poke' sentences move nothing ('click' keeps today's move)
        _say("[ThoughtHand] reader (%s): a touch word while touch is on -- no move (%r)" % (mode, str(r.get("clause") or "")[:60]))
        return {"acted": False, "read": r, "deed": None}
    # 'click' is 'move there, then click' -- the click itself stays refused (intention.REFUSED_VERBS); she moves there
    intent = {"verb": "move", "object": str(r["target"])[:120], "raw": ("reader: " + str(r.get("clause") or ""))[:80]}
    res = door.deed(it, intent, fairy, lane="reader", thought=thought, seeded=seeded, record_refusals=False,
                    trigger=("reader:%s" % str(r.get("clause") or ""))[:120])
    acted = res.get("decision") == "allow"
    _bump("acted" if acted else "deferred")
    out = res.get("outcome") or {}
    _say("[ThoughtHand] reader (%s): WANT %s -> %r (%s) -> %s (%s)%s" % (
        mode, r.get("verb"), intent["object"][:60], r.get("kind"), res.get("decision"), str(res.get("why") or "")[:70],
        (" => " + str(out.get("summary", ""))[:110]) if out else ""))
    return {"acted": acted, "read": r, "deed": res}
