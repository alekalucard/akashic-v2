"""hand_door -- one door for every deed of her hand, whoever offers it. 2026-09-29 (Nous, thought_hand D2; one line in
_note_move changed in thought_hand_r2: an 'unverified' landing is neither an arrival nor a miss).

Ace, 2026-09-29: "if she is actively thinking about moving the mouse her autopilot system should be responding. she only seems
to be able to move a little bit". A second producer of moves (her own words, infrastructure/thought_tap.py) now stands beside
the ask lane (intention.run_cycle); habit_fire is a third, built and unwired. Measured before this (thought_hand sweeps C and
skeptic): gate() and record() are separate critical sections, so a second caller inside the 3-28 s of grounding + reach is
allowed the same deed (sweep C B1/B2); a target the eyes never find was never backed off (60 of 60 offers at a 5 s tick);
execute() re-checked only Ace's idle clock after grounding, never his queued message; a move could start a grounding while his
own grounding was still pending (his eyes wait 8 s, a grounding holds the satellite up to 12 s).

The door, for every lane (reader / ask / habit):
  * ONE CLAIM, non-blocking: a caller that finds the hand busy is deferred and records nothing;
  * Ace first, read LIVE: his queued message or his pending reply defers the deed before the eyes are spent AND again right after
    grounding, before the hand moves (intention.execute calls hook('pre_ground') and hook('pre_actuate'));
  * a motor grounding never starts while his grounding is pending, and at most one motor grounding per GROUND_FLOOR_S;
  * tempo (sweep_c/proto/tempo.py, copied below): the place decides the refractory -- ~5 s to a new place, ~60 s back to one she
    reached, real misses multiply the whole need (x2 each, max x16), ceiling 6 actuations / 60 s -- plus ONE hand deed per
    MOVE_FLOOR_S across ALL lanes (HAND_WINDOW, written by every lane) and an hourly budget of BUDGET_PER_H self-moves (grant
    moves are his gift and do not count);
  * retry limits: a target her eyes cannot find backs off per target key (head noun + kind): 60 s x 2^n, capped at 600 s; the
    not-found still counts as a try at her goal (intention.record -> goal_author.note_outcome) but carries no frustration chord;
  * loop guard: an offer made on a turn seeded by her own deed (a told deed of that place, or a goal / hand surprise) may not
    target the same place; self-seeded deeds are capped at LOOP_MAX_DEPTH within LOOP_WINDOW_S.
It can only make her WAIT or refuse; every floor inside intention.execute (idle >= 5 s, >= 1 s under a grant, the post-grounding
re-check) stays. State lives on _sour_council_shared (HAND_DOOR, HAND_WINDOW) so a hot reload cannot mint a second claim.
Revert: delete this file -- intention._door() returns None and every hook and lane runs today's path.
"""
from __future__ import annotations

import math
import re
import sys
import threading
import time
from collections import deque
from typing import Dict, List, Optional, Sequence

MOVE_FLOOR_S = 20.0            # one hand deed per 20 s across ALL lanes
GROUND_FLOOR_S = 20.0          # at most one MOTOR grounding per 20 s
BUDGET_PER_H = 20              # self-moves per rolling hour without a grant
BACKOFF_BASE_S = 60.0          # a not-found target: 60 s x 2^(n-1), capped
BACKOFF_CAP_S = 600.0
LOOP_WINDOW_S = 600.0          # self-seeded deeds are counted over 10 min
LOOP_MAX_DEPTH = 2
LOOP_SAME_PX = 60.0            # 'the same place' after placement: within this of a seeding deed's landing
ACE_BUSY_MAX_S = 300.0         # sour_council_driver._ACE_BUSY_MAX_S: a reply older than this is not pending
PENDING_MAX_S = 120.0          # vision_ground drops a pending grounding slot after 120 s
TOUCH_VERBS = ("tap", "double_tap", "hold")   # 2026-10-05 (touch set 1): her fingertip's gestures are hand deeds too

# ── tempo: copied from nous_builds/thought_hand/sweep_c/proto/tempo.py (2026-09-29, sweep C), unchanged in behaviour ────────
G_MIN = 5.0
G_MAX = 60.0
D0 = 250.0
TOL_PX = 40.0
WINDOW_S = 600.0
CEIL_PER_MIN = 6
NEED_CAP_S = 300.0


def _dist(a: Sequence[float], b: Sequence[float]) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def refractory_s(target: Sequence[float], hand_xy: Optional[Sequence[float]], history: List[Dict], now: float) -> Dict:
    """need_s = (G_MIN + (G_MAX - G_MIN) * exp(-d_min / D0)) * backoff -- the backoff multiplies the WHOLE need (the code form;
    the design text's 'G_MIN + ... * 2^m' was the typo, skeptic #17)."""
    if hand_xy is not None and _dist(target, hand_xy) <= TOL_PX:
        return {"need_s": None, "since_last_s": None, "allow": False, "why": "no-op: the hand is already there", "d_min": 0.0, "backoff": 1}
    acts = [h for h in history if h.get("actuated")]
    recent = [h for h in acts if now - float(h["t"]) <= WINDOW_S]
    d_min = min([_dist(target, h["target"]) for h in recent if h.get("arrived")] or [float("inf")])
    misses = 0
    for h in reversed(acts):
        if h.get("arrived") is False and not h.get("ace_input_during"):
            misses += 1
        elif h.get("arrived"):
            break
    backoff = 2 ** min(4, misses)
    shape = 0.0 if math.isinf(d_min) else math.exp(-d_min / D0)
    need = min(NEED_CAP_S, (G_MIN + (G_MAX - G_MIN) * shape) * backoff)
    last_t = max([float(h["t"]) for h in acts] or [-1e18])
    since = now - last_t
    in_last_min = sum(1 for h in acts if now - float(h["t"]) < 60.0)
    if in_last_min >= CEIL_PER_MIN:
        return {"need_s": need, "since_last_s": since, "allow": False, "why": "ceiling: %d actuations in the last 60 s" % in_last_min,
                "d_min": d_min, "backoff": backoff}
    ok = since >= need
    return {"need_s": round(need, 2), "since_last_s": round(since, 2), "allow": ok,
            "why": ("refractory %.1f s (nearest reached place %s px, backoff x%d)" % (need, "none" if math.isinf(d_min) else "%.0f" % d_min, backoff)),
            "d_min": d_min, "backoff": backoff}


# ── state (process-global, reload-safe) ─────────────────────────────────────────────────────────────────────────────
def _new_state() -> Dict:
    return {"claim": threading.Lock(), "holder": None, "since": 0.0, "mu": threading.RLock(),
            "window": [0.0, ""],                       # HAND_WINDOW: [ts of the last hand deed, lane] -- every lane writes it
            "moves": deque(maxlen=400),                # {'t','target','arrived','ace_input_during','actuated','lane','grant','key','seeded','idle_s'}
            "grounds": deque(maxlen=400),              # [ts, lane] of every MOTOR grounding the door let start
            "backoff": {},                             # key -> {'n', 'until', 'last'}
            "counters": {"offers": 0, "allowed": 0, "busy": 0, "ace_waiting": 0, "ace_grounding": 0, "ground_floor": 0,
                         "hand_window": 0, "budget": 0, "backoff_hits": 0, "not_found": 0, "tempo": 0, "noop": 0,
                         "loop_same_place": 0, "loop_depth": 0, "post_ground_ace": 0, "deeds": 0, "moves_actuated": 0,
                         "moves_ace_idle_lt30": 0},
            "by_lane": {}}


_LOCAL = _new_state()
_CTX = threading.local()                               # the lane + seed of the deed this thread is inside (for the hooks)


def _st() -> Dict:
    m = sys.modules.get("_sour_council_shared")
    if m is None:
        return _LOCAL
    if not hasattr(m, "HAND_DOOR"):
        m.HAND_DOOR = _LOCAL
    if not hasattr(m, "HAND_WINDOW"):
        m.HAND_WINDOW = m.HAND_DOOR["window"]
    return m.HAND_DOOR


def _count(key: str, lane: str = "") -> None:
    st = _st()
    with st["mu"]:
        st["counters"][key] = st["counters"].get(key, 0) + 1
        if lane:
            bl = st["by_lane"].setdefault(lane, {})
            bl[key] = bl.get(key, 0) + 1


def stats() -> Dict:
    st = _st()
    now = time.time()
    with st["mu"]:
        c = dict(st["counters"])
        c["by_lane"] = {k: dict(v) for k, v in st["by_lane"].items()}
        c["moves_last_hour"] = sum(1 for m in st["moves"] if m.get("actuated") and now - m["t"] <= 3600)
        c["self_moves_last_hour"] = sum(1 for m in st["moves"] if m.get("actuated") and not m.get("grant") and now - m["t"] <= 3600)
        c["groundings_last_hour"] = sum(1 for g in st["grounds"] if now - g[0] <= 3600)
        c["self_loop_depth"] = sum(1 for m in st["moves"] if m.get("seeded") and m.get("actuated") and now - m["t"] <= LOOP_WINDOW_S)
        c["holder"] = st.get("holder")
    return c


def _log(msg: str) -> None:
    try:
        print(("[HandDoor] %s" % msg).encode("ascii", "replace").decode("ascii"), flush=True)   # ASCII only: never the failure
    except Exception:
        pass


# ── Ace, read live ──────────────────────────────────────────────────────────────────────────────────────────────────
def ace_waiting_live() -> bool:
    """His next message is queued, or the council holds his words and has not answered (sour_council_driver.ace_reply_pending,
    read from the shared module so no import of the driver is needed)."""
    m = sys.modules.get("_sour_council_shared")
    if m is None:
        return False
    try:
        if len(getattr(m, "ACE_QUEUE", ()) or ()) > 0:
            return True
        b = float((getattr(m, "ACE_BUSY", None) or [0.0])[0] or 0.0)
        return b > 0.0 and (time.time() - b) < ACE_BUSY_MAX_S
    except Exception:
        return False


def ace_grounding_pending() -> bool:
    """Her eyes are still looking for something Ace named (vision_ground._PENDING holds a slot that is not done)."""
    try:
        vg = sys.modules.get("infrastructure.vision_ground")
        if vg is None:
            return False
        with vg._PENDING_LOCK:
            slots = list(vg._PENDING.values())
        now = time.time()
        return any((not s["done"].is_set()) and now - float(s.get("t0") or 0.0) < PENDING_MAX_S for s in slots)
    except Exception:
        return False


# ── target keys (for the backoff and the loop guard) ────────────────────────────────────────────────────────────────
_GENERIC_HEADS = {"window", "windows", "tab", "ui", "interface", "screen", "desktop", "thing", "area", "spot", "side", "half",
                  "edge", "corner", "part", "place"}


def target_key(obj: str) -> str:
    """name + kind: 'the notepad icon', 'notepad icon on the desktop' and 'the little notepad icon' are ONE place to look for
    (notepad|thing); 'the chat window' and 'the console window' are two. The name is the first word of the phrase that is a
    known head (the reader's lexicon) and not a generic one ('window', 'screen', ...); failing that, the last word."""
    o = str(obj or "").lower()
    ws = re.findall(r"[a-z][a-z\-]*", o)
    kind, heads = "", set()
    try:
        vr = sys.modules.get("infrastructure.volition_read")
        if vr is None:
            from infrastructure import volition_read as vr        # the reader is shipped beside the door
        kind = vr.target_kind(o)
        heads = set(vr._TARGET_HEADS) | set(vr._PERSON_WORDS)
    except Exception:
        kind = ""
    name = next((w for w in ws if w in heads and w not in _GENERIC_HEADS), "")
    if not name:
        name = ws[-1] if ws else ""
    return "%s|%s" % (re.sub(r"[^a-z\-]", "", name), kind)


def _seed_targets(seeded: Optional[Dict], now: float) -> List[Dict]:
    """Her arrived moves of the last LOOP_WINDOW_S whose place the seed names (a told deed / a goal surprise)."""
    if not seeded:
        return []
    text = str(seeded.get("text") or "").lower()
    st = _st()
    with st["mu"]:
        mv = [m for m in st["moves"] if m.get("arrived") and now - m["t"] <= LOOP_WINDOW_S]
    out = []
    for m in mv:
        head = (m.get("key") or "|").split("|")[0]
        if head and re.search(r"\b%s\b" % re.escape(head), text):
            out.append(m)
    return out


# ── the checks ──────────────────────────────────────────────────────────────────────────────────────────────────────
def pre_offer(intent: Dict, lane: str, seeded: Optional[Dict] = None, granted: bool = False, now: Optional[float] = None) -> Optional[str]:
    """Before the gate: why a MOVE may not be offered now, or None."""
    now = time.time() if now is None else now
    st = _st()
    obj = intent.get("object", "")
    key = target_key(obj)
    with st["mu"]:
        last = float(st["window"][0] or 0.0)
        if now - last < MOVE_FLOOR_S:
            _count("hand_window", lane)
            return "one hand deed per %.0f s across every lane: the last was %.0f s ago (%s)" % (MOVE_FLOOR_S, now - last, st["window"][1] or "?")
        if not granted:
            n = sum(1 for m in st["moves"] if m.get("actuated") and not m.get("grant") and now - m["t"] <= 3600)
            if n >= BUDGET_PER_H:
                _count("budget", lane)
                return "hourly budget: %d self-moves in the last hour" % n
        b = st["backoff"].get(key)
        if b and now < float(b["until"]):
            _count("backoff_hits", lane)
            return "her eyes could not find %r %d time(s); looking again in %.0f s" % (key.split("|")[0], b["n"], float(b["until"]) - now)
    if seeded:
        seeds = _seed_targets(seeded, now)
        if any(s.get("key") == key for s in seeds):
            _count("loop_same_place", lane)
            return "this turn was seeded by her own deed at %r: not the same place again" % key.split("|")[0]
        depth = sum(1 for m in list(st["moves"]) if m.get("seeded") and m.get("actuated") and now - m["t"] <= LOOP_WINDOW_S)
        if depth >= LOOP_MAX_DEPTH:
            _count("loop_depth", lane)
            return "self-seeded deeds: %d in the last %d min (cap %d)" % (depth, int(LOOP_WINDOW_S / 60), LOOP_MAX_DEPTH)
    return None


def hook(event: str, **kw) -> Optional[Dict]:
    """Called from intention.execute's move branch. Returns an outcome dict to return INSTEAD of going on, extra outcome fields
    ('not_found'), or None. Every refusal is a deferral: not her deed, no cooldown, no chord."""
    lane = getattr(_CTX, "lane", None) or "direct"
    seeded = getattr(_CTX, "seeded", None)
    obj = str(kw.get("obj") or "")
    st = _st()
    now = time.time()
    if event == "pre_ground":
        if ace_waiting_live():
            _count("ace_waiting", lane)
            return {"ok": False, "summary": "you wanted to move your hand to \"%s\" but Ace was waiting for your answer" % obj, "ms": 0, "deferred": True}
        if ace_grounding_pending():
            _count("ace_grounding", lane)
            return {"ok": False, "summary": "you wanted to move your hand to \"%s\" but your eyes were busy with what Ace said" % obj, "ms": 0, "deferred": True}
        key = target_key(obj)
        with st["mu"]:
            lastg = max([g[0] for g in st["grounds"]] or [0.0])
            if now - lastg < GROUND_FLOOR_S:
                _count("ground_floor", lane)
                return {"ok": False, "summary": "you wanted to move your hand to \"%s\" but your eyes were busy (they looked for a place %.0f s ago)" % (obj, now - lastg), "ms": 0, "deferred": True}
            b = st["backoff"].get(key)
            if b and now < float(b["until"]):
                _count("backoff_hits", lane)
                return {"ok": False, "summary": "you wanted to move your hand to \"%s\" but your eyes had not found it and were resting" % obj, "ms": 0, "deferred": True}
            st["grounds"].append([now, lane])
        _count("groundings", lane)
        return None
    if event == "not_found":
        key = target_key(obj)
        with st["mu"]:
            b = st["backoff"].setdefault(key, {"n": 0, "until": 0.0, "last": 0.0})
            b["n"] += 1
            b["last"] = now
            b["until"] = now + min(BACKOFF_CAP_S, BACKOFF_BASE_S * (2 ** (b["n"] - 1)))
        _count("not_found", lane)
        return {"no_chord": True, "door_backoff_s": round(min(BACKOFF_CAP_S, BACKOFF_BASE_S * (2 ** (b["n"] - 1))), 1)}
    if event == "pre_actuate":
        if ace_waiting_live():
            _count("post_ground_ace", lane)
            return {"ok": False, "summary": "you were about to move your hand to \"%s\" but Ace was waiting for your answer" % obj, "deferred": True}
        target = kw.get("target")
        hand = kw.get("hand")
        with st["mu"]:
            hist = [dict(m) for m in st["moves"]]
        r = refractory_s(target, hand, hist, now) if target is not None else {"allow": True}
        if not r.get("allow"):
            if str(r.get("why", "")).startswith("no-op"):
                _count("noop", lane)
                return {"ok": False, "summary": "you wanted to move your hand to \"%s\" -- it is already there" % obj, "count": False}
            _count("tempo", lane)
            return {"ok": False, "summary": "you were about to move your hand to \"%s\" but you had only just moved it (%s)" % (obj, r.get("why")), "deferred": True}
        if seeded and target is not None:
            for s in _seed_targets(seeded, now):
                if s.get("target") is not None and _dist(target, s["target"]) <= LOOP_SAME_PX:
                    _count("loop_same_place", lane)
                    return {"ok": False, "summary": "you were about to move your hand back to \"%s\", where it had just been" % obj, "deferred": True}
        _CTX.idle_s = kw.get("idle")
        return None
    return None


# ── the deed ────────────────────────────────────────────────────────────────────────────────────────────────────────
# 2026-10-05 (Nous, touch_screen set 1; S12, FS12.6): a fresh nonce per deed, minted while the claim is held and cleared when it
# is released. infrastructure/touch_os.press refuses any request whose nonce is not the current one. Said honestly: this stops
# accidental and re-entrant callers; any code in her process could read it -- the real fences are cell T0's static tests.
def deed_nonce() -> Optional[str]:
    return _st().get("nonce")


def _touch_live(it, verb: str) -> bool:
    """A touch verb is a hand deed only while touch's switch offers it (intention._touch_verbs); absent = today's path."""
    if verb not in TOUCH_VERBS:
        return False
    try:
        return verb in it._touch_verbs()
    except Exception:
        return False


def _note_move(intent: Dict, out: Dict, lane: str, seeded: Optional[Dict], granted: bool) -> None:
    """Bookkeeping after an allowed move: HAND_WINDOW, the tempo history, the backoff reset."""
    if not out or out.get("deferred") or out.get("target") is None:
        return
    hand = out.get("hand") or {}
    now = time.time()
    idle = getattr(_CTX, "idle_s", None)
    # 2026-09-29 (thought_hand_r2): ok None = the landing could not be checked (hand_target 'unverified'): neither an arrival
    # (no d_min credit, no backoff reset) nor a miss (no x2 backoff) -- tempo's miss count reads `arrived is False` only
    rec = {"t": now, "target": tuple(out["target"]), "arrived": (None if out.get("ok") is None else bool(out.get("ok"))), "actuated": True, "lane": lane,
           "ace_input_during": bool(hand.get("input_during_reach")) or bool(hand.get("carry_evidence")),
           "grant": bool(granted), "key": target_key(intent.get("object", "")), "seeded": bool(seeded), "idle_s": idle}
    st = _st()
    with st["mu"]:
        st["moves"].append(rec)
        st["window"][0], st["window"][1] = now, lane
        if rec["arrived"]:
            st["backoff"].pop(rec["key"], None)
    _count("moves_actuated", lane)
    if idle is not None and float(idle) < 30.0:
        _count("moves_ace_idle_lt30", lane)


def _ef(key: str) -> bool:
    """eyes_fix_1009: one key of Ace's eyes switch (state/eyes_fix.json, infrastructure/eyes_fix.py); OFF on any doubt (the
    module absent, the file absent or malformed) -- then every line marked eyes_fix runs today's path."""
    try:
        from infrastructure import eyes_fix as _efm
        return _efm.on(key)
    except Exception:
        return False


def _untouched(it, intent: Dict, d: Dict, recorded: bool, words: Optional[str] = None) -> Optional[Dict]:
    """eyes_fix F10 'touch_tell' (DIAGNOSIS C10, ledger rows 418 / 419): a touch the door or the gate DEFERRED is told as not
    having happened, in set 1c's words -- 'your finger did not touch it'. Before this a gate deferral had no outcome, so
    intention.record appended nothing to _RESULTS and she was told nothing at all. recorded=True: intention.record carries it
    (the ask lane's one ledger row, now with its words); else it goes to _RESULTS only (no ledger row, no deed). words = her
    words for the reason when d['why'] is the door's own text (the busy claim, verify m1). None = key off."""
    try:
        if not _ef("touch_tell"):
            return None
        verb = str(intent.get("verb") or "")
        n = re.sub(r"^(?:the|a|an)\s+", "", " ".join(str(intent.get("object") or "").split())[:60], flags=re.I) or "it"
        out = {"ok": False, "count": False, "deferred": True, "no_chord": True, "ms": 0,
               "summary": "you wanted to %s the %s; %s; your finger did not touch it" % (verb.replace("_", " "), n,
                                                                                         words or d.get("why") or "it was not the moment"),
               "touch": {"verdict": "deferred", "reason": "gate", "why": str(d.get("why") or "")[:120], "gesture": verb, "item": n}}
        if not recorded:
            with it._LOCK:
                it._RESULTS.append((time.time(), out["summary"], {"verb": verb, "obj": intent.get("object", ""), "ok": False,
                                                                   "lane": None, "deferred": True, "pos": None, "before": None,
                                                                   "after": None, "hand": None}))
        return out
    except Exception:
        return None


def deed(it, intent: Dict, fairy=None, lane: str = "?", thought: str = "", ace_waiting: bool = False,
         seeded: Optional[Dict] = None, record_refusals: bool = False, record_fn=None, trigger: Optional[str] = None) -> Dict:
    """claim -> Ace live -> (move) pre_offer -> gate -> execute (hooks) -> record -> bookkeeping. Returns
    {'decision', 'why', 'gate', 'outcome', 'lane'}. A door refusal is a deferral: no deed, no cooldown, no chord; it is written
    to the ledger only when record_refusals (the ask lane keeps today's one row per non-none intent)."""
    verb = intent.get("verb", "none")
    if verb == "none":
        return {"decision": "none", "why": "nothing wanted", "gate": {"decision": "none", "why": "nothing wanted"}, "outcome": None, "lane": lane}
    _count("offers", lane)
    st = _st()
    if not st["claim"].acquire(blocking=False):
        _count("busy", lane)
        why = "hand busy (%s is mid-deed, %.1f s)" % (st.get("holder"), time.time() - float(st.get("since") or 0.0))
        d = {"decision": "defer", "why": why}
        _told = (_untouched(it, intent, d, record_refusals,
                            words="your hand was busy with another of your deeds, so this one did not start")
                 if verb in TOUCH_VERBS else None)   # eyes_fix F10 (verify m1 / VT01): the busy door's touch deferral is told too
        if record_refusals:
            _rec(it, thought, intent, d, _told, fairy, record_fn, lane, trigger)
        return {"decision": "defer", "why": why, "gate": d, "outcome": None, "lane": lane}
    st["holder"], st["since"] = lane, time.time()
    try:
        import secrets as _secrets                     # 2026-10-05 (touch set 1): this deed's nonce
        st["nonce"] = _secrets.token_hex(12)
    except Exception:
        st["nonce"] = None
    try:
        granted = False
        try:
            granted = bool(it.grant_active())
        except Exception:
            granted = False
        why = None
        if ace_waiting or ace_waiting_live():
            _count("ace_waiting", lane)
            why = "Ace is waiting for an answer"
        elif verb == "move" or _touch_live(it, verb):   # touch set 1: one hand deed per 20 s, the budget and backoff for touch too
            why = pre_offer(intent, lane, seeded, granted=granted)
        if why:
            d = {"decision": "defer", "why": why}
            _told = _untouched(it, intent, d, record_refusals) if verb in TOUCH_VERBS else None   # eyes_fix F10
            if record_refusals:
                _rec(it, thought, intent, d, _told, fairy, record_fn, lane, trigger)
            _log("%s: %s %r -> defer (%s)" % (lane, verb, str(intent.get("object", ""))[:60], why[:90]))
            return {"decision": "defer", "why": why, "gate": d, "outcome": None, "lane": lane}
        d = it.gate(intent, ace_waiting=False)
        if d.get("decision") != "allow":
            _told = (_untouched(it, intent, d, record_refusals)
                     if (verb in TOUCH_VERBS and d.get("decision") == "defer") else None)   # eyes_fix F10: rows 418 / 419
            if record_refusals:
                _rec(it, thought, intent, d, _told, fairy, record_fn, lane, trigger)
            return {"decision": d.get("decision"), "why": d.get("why"), "gate": d, "outcome": None, "lane": lane}
        _count("allowed", lane)
        _CTX.lane, _CTX.seeded, _CTX.idle_s = lane, seeded, None
        try:
            out = it.execute(intent, fairy)
        finally:
            _CTX.lane, _CTX.seeded = None, None
        _rec(it, thought, intent, d, out, fairy, record_fn, lane, trigger)
        if verb == "move" or (verb in TOUCH_VERBS and isinstance(out, dict) and out.get("touch")):   # touch set 1
            _note_move(intent, out, lane, seeded, granted)
        if out and not out.get("deferred"):
            _count("deeds", lane)
        _log("%s: %s %r -> %s%s | %s" % (lane, verb, str(intent.get("object", ""))[:60], "done" if out and not out.get("deferred") else "deferred",
                                         (" ok=%s" % out.get("ok")) if out else "", _brief()))
        return {"decision": "allow", "why": d.get("why"), "gate": d, "outcome": out, "lane": lane}
    finally:
        st["holder"], st["since"] = None, 0.0
        st["nonce"] = None                             # touch set 1: the nonce dies with the claim
        st["claim"].release()


def _rec(it, thought, intent, d, out, fairy, record_fn, lane, trigger) -> None:
    try:
        if record_fn is not None:
            record_fn(d, out)
        else:
            dd = dict(d)
            if trigger:
                dd["trigger"] = trigger
            it.record(thought, intent, dd, out, fairy)
    except Exception as e:
        _log("record: %s" % e)


def _brief() -> str:
    s = stats()
    return ("moves/h %d (self %d of %d), groundings/h %d, backoff hits %d, tempo %d, loop %d+%d, ace-live %d/%d, idle<30s moves %d"
            % (s["moves_last_hour"], s["self_moves_last_hour"], BUDGET_PER_H, s["groundings_last_hour"], s["backoff_hits"],
               s["tempo"], s["loop_same_place"], s["loop_depth"], s["ace_waiting"], s["post_ground_ace"], s["moves_ace_idle_lt30"]))
