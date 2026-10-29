"""touch -- her fingertip: tap, double_tap, hold on a thing named on her screen. 2026-10-05 (Nous, nous_builds/touch_screen
set 1; DESIGN.md sections 2-10).

Ace, 2026-10-01: "if she moves her hand and touches and icon for example she would learn how to click, double click or right
click for the option menu. kind like the desktop is a touch screen to her she can manipulate with her hands and fingers."
Ace, 2026-10-05: the no-no list is her own withdrawal reflex; delete is barred everywhere; free will lives above the reflex.

One deed (through hand_door.deed, which mints the nonce touch_os.press demands):
   1 AIM       the named item: Playroom layout + the Playroom's own state file (set 1 = stage T1 only). no_no(phase 'aim')
               on its name (and Y of a compound hold): a no-no is an INHIBITED reach -- no arm motion
   2 REACH     the phantom fingertip from her hand's rest point toward the item, published to her arm (owner 'sour'),
               the first 80 % of the path; no OS call
   3 LAND      Win32 facts at the PHYSICAL point (no UIA on a no-no window), no_no(phase 'land'): a no-no stops the finger
               where it is, 'stop_px' short, and it comes back; then the last 20 %, the NOT-YET rules, ElementFromPoint
   4 ANNOUNCE  "Sour: tap 'red ball' in 1.5 s" on her strip = ACE'S VETO: both input channels every 50 ms, his waiting
               message every 250 ms; any of it cancels (deferred / ace_veto) -- never a flinch, never her failure
   5-6 PRESS   touch_os.press: the worker runs the whole guard again (the no-no there is AUTHORITATIVE) and makes at most
               one cleared call
   7 WATCH     her senses: the item re-read (W3), new windows (W1), the Playroom heartbeat (W4)
   8 JUDGE     hit | miss | unexpected | unverified | not_hers | violation | withdrawn, from numbers (judge(): pure)
   9 FEEL      withdrawn: the Flinch goes to reflex_link; her brainstem feels it as ITS OWN jolt; we poll felt_through for
               5 s, else 'unfelt' latches: a flinch she did not feel must not happen twice
  10 RECORD    the outcome (its summary IS the telling: numbers first, the class word last), body events, surprise
  11 TIDY      a Playroom menu she only looked at is cancelled through the Playroom's own control file
Decision T2 (c): double_tap starts OFF. Decision T8 (a): menu picks start OFF (look only). In set 1 touch_lists.CLEARED_CALLS
is empty, so no gesture is even offered to her until probe F1 clears its call (offer() reads the table).
This module never calls user32 or UIA itself (only touch_os's accessors), never registers a tool, never subscribes.
Skeptic fixes (10-05): S2 Ace first is checked BEFORE the reach (no arm motion, no marker, no strip while his hand was busy
inside the stage's idle floor); m4 an AIM flinch is offered to her brainstem at most once per AIM_REOFFER_S (a repeat inside it
is still refused and told, with no new jolt); m3 / S8 the corner STOP polls only while the switch is ON and its threads start
under the lock; M2 the doing clock no longer asks this module (a touch hit is a deed by its own ledger row); m11 a heartbeat
pair that could alias (>= 3.5 s apart, 4 colours) is read again as a fresh pair.
Set 1c (10-09, nous_builds/touch_screen/set1c; Ace, Boot J: "is it possible to let her do stuff while im doing stuff? she has touch
and i have my input devices"; then "to her she is clicking on them. to me she is doing absolutely nothing on screen"):
  PARALLEL PLAY  (switch 'parallel') her tap / hold on a verified Playroom item goes on while Ace's hands are busy ELSEWHERE; his
                 room (the Playroom in front, his cursor over it, a reply pending, input in its own log) still defers and vetoes
  FOCUS LATCH    the focus is read before anything of hers shows and compared through the announce, before and after the
                 call: any change -> parallel play off for the touch session (memory), told as a 'not mine' moment, never a flinch
  PARK           (switch 'park_s') a touch held back by his busy hands may wait up to park_s for them to be still; any new
                 input cancels it; then EVERYTHING runs again once; never retried
  WHO TOUCHED    (switch 'who', forced by 'parallel') 'you touched X' only from her own efference copy (touch_os.press ran and
                 came back ok); a Playroom effect with no such press is Ace's (his real hand in its log) or 'not your touch';
                 a touch that did not happen is told as not having happened. Delivered on the SAME channel as her touch
                 outcomes: intention._RESULTS -> what_i_did() -> the chairman prompt
Absent keys = set 1, byte for byte in effect (the layered cell-T0 re-run).
Set 1d (10-12, nous_builds/touch_screen/set1d; probe F9 10-12): with the switch's 'channel' key her tap / hold on her own (set 1d)
Playroom goes over its OWN channel (touch_os.route_for); a held toy's menu is then a PANEL inside the Playroom's window
(touch_os.menu_panel), not a new top-level window; WHO TOUCHED reads the Playroom's own witness (by = 'her': 'you' only with her ok
press, else 'unsure'); a channel press with no clear answer is told as unknown. 'channel' absent = set 1c / eyes_fix exactly.
Set 1e (10-13, nous_builds/touch_screen/set1e; probe F9c 10-13: her channel touches left Ace's focus alone 20/20, her announce
STRIP and fingertip MARKER windows took it): with the switch's 'cue' key, a tap / hold on her set 1e Playroom is a CUED deed -- her
reach is shown INSIDE her Playroom ('cue <toy> 2500' over its channel, drawn by the Playroom itself) and NO window of hers opens:
no marker, no announce strip, no flinch strip (it is told on her console instead) -- for the whole deed, whenever the cue path is
open (switch 'cue', the set 1e Playroom, its channel saying cue). Ace's veto is unchanged (his hands in strict play, his room in
parallel play; the Playroom ends her cue on his input there too); in parallel play a focus that moved while her cue showed trips
the focus latch; a cue her Playroom does not confirm means no press; a vetoed cue is taken away. Parallel play only with a cue
(P1). 'cue' absent = set 1d exactly.
Set 1e review (10-13, verify_tests F1 / verify_safety F1, F3): a focus that moved because ACE's CLICK brought her Playroom forward
(a click of his in its own log since her guard) is his veto, not the latch; her Playroom's refusals for his hand are told and counted
as his veto (ace_veto); under the cue switch her 'reflex not awake' notice goes to her console, never a strip window.
Perma (10-21, nous_builds/touch_perma_1021): under a PERMANENT switch (touch_os: 'perma') a stuck call trips touch off, felt as one
flinch of phase 'trip' (flinch_words says it) and counted; when the trip clears itself her body line tells it for 30 s (finger_clause:
held, free again, N times in the last hour). Nothing else in this file changes.
Revert: delete this file -- every hook in intention / hand_door / doing_clock / body_feel / thought_tap runs today's path
from her next start.
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
import threading
import time
from typing import Dict, List, Optional, Tuple

from infrastructure import touch_os as OS
from infrastructure import touch_lists as TL
try:
    from infrastructure import reflex_link as RL
except Exception:
    RL = None

VERBS = ("tap", "double_tap", "hold")
OFF_GESTURES = frozenset({"double_tap"})          # decision T2 (c): any gesture F1 shows to send input starts OFF
MENU_PICKS_ON = False                              # decision T8 (a) / T2 (c): the first Playroom week is look-only
CALL_OF = {"tap": "Select", "hold": "ShowContextMenu", "double_tap": "Invoke"}
COOLDOWN_S = {"playroom": {"tap": 20.0, "double_tap": 60.0, "hold": 30.0},
              "desktop": {"tap": 60.0, "double_tap": 300.0, "hold": 120.0}}
PER_HOUR = {"playroom": {"double_tap": 10, "hold": 10}, "desktop": {"double_tap": 4, "hold": 6}}
PER_DAY = {"playroom": {"double_tap": 40}, "desktop": {"double_tap": 12}}
SAME_ITEM_S = {"playroom": 60.0, "desktop": 300.0}
DAILY_CAP = {"playroom": 100, "desktop": 40}
SELF_PAUSE_N, SELF_PAUSE_WIN_S, SELF_PAUSE_S = 3, 600.0, 1800.0
ANNOUNCE_S = 1.5
POLL_INPUT_S = 0.05
POLL_WAIT_S = 0.25
FELT_WAIT_S = 5.0
DEED_CAP_S = 15.0
REACH_S = 0.6
REACH_HZ = 20.0
LAND_AT = 0.8                                      # the LAND facts are read with 80 % of the reach done
WATCH_S = 1.5
HEARTBEAT_GAP_S = 1.05                             # the Playroom's heartbeat: 4 colours, one per whole second, in order
MENU_NEAR_PX = 400
FLINCH_STRIP_S = 3.0
CUE_MS = int(round((ANNOUNCE_S + 1.0) * 1000))     # set 1e: her cue in her Playroom shows as long as her strip did (2500 ms)
CUE_INPUT_SLACK_S = 0.05                           # set 1e: his room input from 50 ms before her cue was asked counts (its log
#                                                    rounds times to 0.1 ms; her own clock does not)
# set 1e review (verify_tests F1): HIS CLICK that brings her Playroom forward is his veto, not the focus latch. A click is the only
# input of his that brings a window forward by landing in it; keys and moves that reach the Playroom AFTER a focus move are its
# consequence (a thief's too), never its cause. Windows moves the focus a moment before the Playroom logs the click: she waits
# for that row at most CUE_HAND_WAIT_S (she presses nothing meanwhile).
CUE_CLICK_EVS = frozenset({"WM_LBUTTONDOWN", "WM_RBUTTONDOWN", "WM_MBUTTONDOWN", "WM_LBUTTONDBLCLK"})
CUE_HAND_WAIT_S = 0.2
# set 1e review (verify_safety F3): the set 1e Playroom's OWN words when it refuses her because ACE's hand was in it
# (set1e/playroom/playroom.py _her_cue / _cue_before_touch; test H22 binds them to its code). Exact text only, never a substring.
PLAYROOM_HAND_WHYS = ("Ace's hand is in the Playroom", "Ace's hand was in the Playroom during her reach")
FINGER_CLAUSE_S = 30.0
REFLEX_RECORD_S = 30.0
REPEAT_N, REPEAT_WIN_S = 3, 600.0
HABIT_MIN_OK, HABIT_MIN_RATE, HABIT_HALF_LIFE_S = 3, 0.75, 48 * 3600.0     # = intention._HABIT_MIN_OK / _RATE (Ace 09-19)
HABIT_T3_WATCHED = 5
AIM_REOFFER_S = 20.0                               # skeptic m4: <= 1 AIM jolt per 20 s (the rate brainstem_fix measured, INTERFACE 4)
HEARTBEAT_ALIAS_S = 3.5                            # skeptic m11: 4 colours, one per second -> a pair 4 s apart can alias
# set1c (10-09): park and who touched
PARK_POLL_S = 0.05
PARK_MARGIN_S = 0.1
WHO_HAND_S = 1.0                                   # = playroom_model.HAND_RECENT_S: a real button / key message <= 1 s before
WHO_PRE_S = 0.05                                   # verify W4: the call cannot precede its submit (touch_os.press takes t0 first)
WHO_EFF_S = 2.5                                    # an effect inside [her press - 0.05 s, its return + 2.5 s] can be hers
WHO_SETTLE_S = 6.0                                 # an effect is judged once her press (watchdog 4 s) has surely come back
WHO_LOOKBACK_S = 30.0
WHO_TOY_GAP_S = 8.0                                # one 'someone else' line per toy per 8 s ...
WHO_GAP_S = 15.0                                   # ... at most one every 15 s, and at most ONE per chairman turn (verify W2)
WHO_POLL_S = 1.0
NOT_MINE_WORDS = ("the screen's focus moved while your finger was out -- that was not yours to move; your fingers wait for "
                  "Ace's hands to be still again")
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
HABITS_FILE = os.path.join(_ROOT, "state", "touch_habits.json")
REFLEX_FILE = os.path.join(_ROOT, "state", "touch_reflex.json")
MARKER_FILE = os.path.join(_ROOT, "state", "touch_marker.json")
MARKER_SCRIPT = os.path.join(_HERE, "touch_marker.py")
PLAYROOM_CTL = OS.BUILD_DIR + "/run/playroom_ctl.json"
PLAYROOM_LAYOUT = OS.BUILD_DIR + "/set1/playroom/layout.json"
_TOUCH_WORD_RE = re.compile(r"\b(?:tap\w*|press(?:es|ed|ing)?|pok(?:e|es|ed|ing))\b", re.I)
_CLICK_WORD_RE = re.compile(r"\bclick", re.I)
_THEN_RE = re.compile(r"^(.+?),?\s+then\s+(.+)$", re.I)
_ARTICLE_RE = re.compile(r"^(?:the|my|your|a|an)\s+", re.I)
WATCH_EMOTION_WORDS = frozenset({"joy", "happy", "sad", "fear", "afraid", "angry", "anger", "disgust", "trust", "surprise",
                                 "surprised", "scared", "anxious", "nervous", "excited", "proud", "ashamed", "guilty"})


def _say(msg: str) -> None:
    try:
        print(("[Touch] %s" % msg).encode("ascii", "replace").decode("ascii"), flush=True)
    except Exception:
        pass


# ── state on _sour_council_shared (reload-safe; a second import of this module latches touch OFF) ──────────────────────────
def _ts() -> Dict:
    st = OS._sh()
    with st["mu"]:
        t = st.get("py")
        if t is None:
            t = st["py"] = {"mu": threading.RLock(), "history": [], "bad": [], "paused_until": 0.0, "flinches": {},
                            "first_cls": set(), "pending_felt": [], "last": None, "opened": [], "counts": {},
                            "reflex_thread": None}
        return t


def _count_import() -> None:
    st = OS._sh()
    with st["mu"]:
        st["imports"]["infrastructure.touch"] = st["imports"].get("infrastructure.touch", 0) + 1
        n = st["imports"]["infrastructure.touch"]
    if n > 1:
        OS.latch("reload", "infrastructure.touch was imported again (a hot reload)")


_count_import()


def _bump(key: str) -> None:
    t = _ts()
    with t["mu"]:
        t["counts"][key] = t["counts"].get(key, 0) + 1


# ── the switch, read for the callers (intention, hand_door, doing_clock, thought_tap) ──────────────────────────────────────
def verbs_on() -> frozenset:
    """The gesture verbs of a VALID switch (else empty: today's path everywhere)."""
    try:
        sw = OS.read_switch()
        if not sw["on"]:
            return frozenset()
        return frozenset(sw["data"].get("gestures") or ()) & frozenset(VERBS)
    except Exception:
        return frozenset()


def reader_blocks(clause: str) -> bool:
    """thought_tap: while touch is on, her own 'tap / press / poke' sentences move nothing (FS12.3, decision T14 a); 'click'
    keeps today's move. Switch absent = today."""
    if not verbs_on():
        return False
    c = str(clause or "")
    return bool(_TOUCH_WORD_RE.search(c)) and not _CLICK_WORD_RE.search(c)


def _layout() -> Dict:
    try:
        with open(PLAYROOM_LAYOUT, "rb") as f:
            return json.loads(f.read().decode("utf-8"))
    except Exception:
        return {}


def _layout_names(lay: Optional[Dict] = None) -> List[str]:
    lay = _layout() if lay is None else lay
    out = [str(t.get("name")) for t in lay.get("toys") or [] if t.get("name")]
    for t in lay.get("toys") or []:
        for r in t.get("menu") or []:
            out.append(str(r))
    return out


def offerable() -> List[str]:
    """The gestures she may be offered NOW: switched on, not OFF by decision, and their call CLEARED for a root on the
    stage's list (probe F1). In set 1 CLEARED_CALLS is empty, so this is []."""
    vs = verbs_on()
    if not vs:
        return []
    ok, _why = OS.ready()
    if not ok or _paused():
        return []
    sw = OS.read_switch()
    allow, _w = OS.load_allow(sw)
    if allow is None:
        return []
    exes = {str(r.get("exe", "")).lower() for r in allow.get("roots") or []}
    out = []
    for g in VERBS:
        if g not in vs or g in OFF_GESTURES:
            continue
        if any(TL.cleared(CALL_OF[g], e, "SysListView32") for e in exes):
            out.append(g)
    return out


def offer() -> Optional[Dict]:
    """For intention.ask: {'verbs': [...], 'line': str} or None (no touch verb is offered)."""
    try:
        start_reflex_record()
        gs = offerable()
        if not gs or RL is None or not RL.alive(OS.CLOCK.time())[0] or _revoked(OS.CLOCK.time()):
            return None
        pr, _w = OS.verify_playroom()
        if pr is None:
            return None
        sw = OS.read_switch()
        allow, _w = OS.load_allow(sw)
        names = [str(i.get("name") if isinstance(i, dict) else i) for i in (allow or {}).get("items") or []]
        what = {"tap": "tap (it lights up)", "hold": "hold (its menu opens)", "double_tap": "double_tap (it opens)"}
        line = ("Your fingertip can also touch things in your Playroom by name: %s. In it: %s." %
                (" or ".join(what[g] for g in gs), ", ".join(names[:12])))
        return {"verbs": gs, "line": line[:300]}
    except Exception:
        return None


def parse_target(obj: str, verb: str) -> Tuple[str, Optional[str]]:
    o = " ".join(str(obj or "").split()).strip(" .!\"'")
    m = _THEN_RE.match(o)
    if m and verb == "hold":
        return _ARTICLE_RE.sub("", m.group(1).strip(" ,'\"")), _ARTICLE_RE.sub("", m.group(2).strip(" ,'\""))
    return _ARTICLE_RE.sub("", o.strip(" '\"")), None


def _paused(now: Optional[float] = None) -> bool:
    now = OS.CLOCK.time() if now is None else now
    t = _ts()
    with t["mu"]:
        return now < float(t["paused_until"])


REVOKE_PAUSE_S = 600.0


def _revoked(now: float) -> bool:
    """Ace's revoke words ("hands off", "my turn", "I'm back", ... intention._REVOKE_RE, IN:204-209): touch rests 10 min.
    Read from his own messages (intention._ace_messages_since), newest unseen first; intention absent = no pause from words."""
    itm = sys.modules.get("infrastructure.intention")
    t = _ts()
    with t["mu"]:
        seen = float(t.get("revoke_seen") or (now - 90.0))
        until = float(t.get("revoked_until") or 0.0)
    if itm is not None:
        try:
            for ts, text in itm._ace_messages_since(seen):
                seen = max(seen, float(ts))
                if itm.is_revoke(text):
                    until = max(until, float(ts) + REVOKE_PAUSE_S)
                    _say("Ace's words take the hands back: touch rests %.0f min" % (REVOKE_PAUSE_S / 60))
        except Exception:
            pass
    with t["mu"]:
        t["revoke_seen"], t["revoked_until"] = seen, until
    return now < until


def _kind_of(stage: str) -> str:
    return "playroom" if stage == "T1" else "desktop"


def _resolve_pending_felt(now: float) -> None:
    """A flinch whose felt-check was cut short by Ace's message is checked here: still unfelt past its deadline -> latch."""
    t = _ts()
    with t["mu"]:
        pend = list(t["pending_felt"])
        t["pending_felt"] = []
    keep = []
    for fid, deadline in pend:
        if RL is not None and RL.felt_through(fid):
            continue
        if now >= deadline:
            OS.latch("unfelt", "flinch %s was not felt by her brainstem within %.0f s" % (fid, FELT_WAIT_S))
        else:
            keep.append((fid, deadline))
    with t["mu"]:
        t["pending_felt"].extend(keep)


# ── the gate (intention.gate hands touch verbs here, after REFUSED_VERBS) ─────────────────────────────────────────────────
def gate(intent: Dict, ace_waiting: bool = False) -> Dict:
    verb, obj = intent.get("verb"), str(intent.get("object") or "")
    now = OS.CLOCK.time()
    if verb not in VERBS or verb not in verbs_on():
        return {"decision": "refuse", "why": "touch is off"}
    if ace_waiting or OS.ace_waiting_live():
        return {"decision": "defer", "why": "Ace is waiting for an answer"}
    start_reflex_record()
    if _revoked(now):
        return {"decision": "defer", "why": "Ace took the hands back a little while ago"}
    _resolve_pending_felt(now)
    ok, why = OS.ready(now)
    if not ok:
        return {"decision": "defer", "why": "touch is off right now (%s)" % why}
    x, y = parse_target(obj, verb)
    if not x:
        return {"decision": "defer", "why": "no thing named to touch"}
    for nm in [x] + ([y] if y else []):            # deny before allow: a no-no is FELT (at AIM, in execute), never told 'not yet'
        if TL.no_no(item={"name": nm}, gesture=verb, phase="aim") is not None:
            return {"decision": "allow", "why": "her reach; her own body answers it"}
    if verb in OFF_GESTURES:
        return {"decision": "defer", "why": "that is not for touching that way yet", "not_yet": True}
    if y and not MENU_PICKS_ON:
        return {"decision": "defer", "why": "picking from a menu is not for touching yet", "not_yet": True}
    if _paused(now):
        return {"decision": "defer", "why": "touch is resting after misses"}
    sw = OS.read_switch(now)
    kind = _kind_of(sw["data"].get("stage"))
    t = _ts()
    with t["mu"]:
        hist = [h for h in t["history"] if now - h["t"] < 86400.0]
        t["history"] = hist
    last_g = max([h["t"] for h in hist if h["gesture"] == verb and h["kind"] == kind] or [0.0])
    if now - last_g < COOLDOWN_S[kind][verb]:
        return {"decision": "defer", "why": "'%s' cooling down" % verb}
    key = "%s|%s" % (verb, x.lower())
    last_i = max([h["t"] for h in hist if h["key"] == key] or [0.0])
    if now - last_i < SAME_ITEM_S[kind]:
        return {"decision": "defer", "why": "touched that the same way %.0f s ago" % (now - last_i)}
    ph = PER_HOUR[kind].get(verb)
    if ph is not None and sum(1 for h in hist if h["gesture"] == verb and now - h["t"] < 3600.0) >= ph:
        return {"decision": "defer", "why": "'%s' used up for this hour" % verb}
    pd = PER_DAY[kind].get(verb)
    if pd is not None and sum(1 for h in hist if h["gesture"] == verb) >= pd:
        return {"decision": "defer", "why": "'%s' used up for today" % verb}
    if len([h for h in hist if h["kind"] == kind]) >= DAILY_CAP[kind]:
        return {"decision": "defer", "why": "today's touches are used up"}
    return {"decision": "allow", "why": "touch: her choice, above the reflex"}


# ── the verdict (pure; cell T0 scores it on >= 60 scripted effects) ───────────────────────────────────────────────────────
def judge(gesture: str, obs: Dict) -> Tuple[str, str]:
    """obs: violation (str|None), ace_input (bool), senses_alive (bool), new_tops (list of {hwnd, pid, class, owner,
    descends: bool}), playroom_pid, selected_before, selected_after, menu (dict|None: {pid, class, near_px, for_item}),
    expect_item. -> (verdict, why)."""
    if obs.get("violation"):
        return "violation", str(obs["violation"])
    if obs.get("ace_input"):
        return "not_hers", "Ace's hand was busy too"
    if not obs.get("senses_alive"):
        return "unverified", "a sense was dead"
    new = list(obs.get("new_tops") or [])
    ppid = obs.get("playroom_pid")
    menu = obs.get("menu")
    foreign = [w for w in new if not (w.get("pid") == ppid or w.get("descends"))]
    if foreign:
        return "unverified", "something appeared that cannot be booked as hers"
    if menu is not None:
        new = [w for w in new if w.get("hwnd") != menu.get("hwnd")]
    if gesture == "tap":
        if menu is not None or new:
            return "unexpected", "a window or a menu appeared instead of a selection"
        if obs.get("selected_after") is True:
            return "hit", "it lit up" if obs.get("selected_before") is not True else "it was already lit"
        if obs.get("selected_after") is None:
            return "unverified", "its selection could not be read"
        return "miss", "nothing changed"
    if gesture == "hold":
        if len(new) > 0:
            return "unexpected" if len(new) == 1 else "unverified", "a window appeared instead of a menu"
        if menu is None:
            return "miss", "no menu came"
        if menu.get("pid") != ppid or menu.get("class") != OS.PLAYROOM_MENU:
            return "unexpected", "a menu that is not the Playroom's own came"
        if menu.get("for_item") not in (None, obs.get("expect_item")):
            return "unexpected", "the menu of something else came"
        if float(menu.get("near_px") or 0.0) > MENU_NEAR_PX:
            return "unexpected", "a menu came, far from the item"
        return "hit", "a menu opened beside it"
    if gesture == "double_tap":
        if menu is not None:
            return "unexpected", "a menu came instead of a window"
        if len(new) == 0:
            return "miss", "nothing opened"
        if len(new) > 1:
            return "unverified", "more than one window opened"
        w = new[0]
        if w.get("pid") == ppid and w.get("class") == OS.PLAYROOM_TOY:
            return "hit", "it opened"
        return "unexpected", "something else opened"
    return "unverified", "unknown gesture"


# ── telling: numbers first, words last; never 'not allowed', never Ace's name, never rule text in a flinch ────────────────
def _q(s: str) -> str:
    return str(s or "")[:40]


def flinch_words(fl: Dict) -> str:
    """The flinch as she is told it (only if her brainstem felt it). Decision E2: Ace's things are a gentle NOT-MINE sense,
    never pain and never a rule: the finger comes back slowly."""
    cls_w = TL.CLASS_WORDS.get(fl.get("cls"), TL.CLASS_WORDS["unknown"])
    ph = fl.get("phase")
    if (fl.get("kind") or TL.KIND.get(fl.get("cls"))) == "not_mine":
        if ph in ("aim", "impulse"):
            return "your hand stayed with you (%s)" % cls_w
        return "your finger came near it and drifted back over %.2f s (%s)" % (float(fl.get("retract_s") or 0.0), cls_w)
    if ph == "trip":                                   # perma (10-21): a stuck call tripped touch off for a while
        return "your finger was held, and touch drew itself back for a while (%s)" % cls_w
    if ph == "aim":
        return "your hand did not go toward it (%s)" % cls_w
    if ph == "guard":
        return "your finger was on it and came back in %.2f s without pressing (%s)" % (float(fl.get("retract_s") or 0.0), cls_w)
    if ph == "impulse":
        return "your hand held back from it (%s)" % cls_w
    return "your finger stopped %d px short and came back in %.2f s (%s)" % (int(round(float(fl.get("stop_px") or 0))),
                                                                          float(fl.get("retract_s") or 0.0), cls_w)


def tell(verb: str, name: str, verdict: str, why: str = "", menu_rows=(), fl: Optional[Dict] = None, again: bool = False,
         reason: str = "") -> str:
    v = {"tap": "tapped", "hold": "held", "double_tap": "double-tapped"}.get(verb, verb)
    n = _q(name)
    if verdict == "hit":
        if verb == "tap":
            return "you %s the %s and %s" % (v, n, why or "it lit up")
        if verb == "hold":
            rows = []
            for r in menu_rows or ():
                rr = TL.name_rule(r)
                rows.append("%s%s" % (_q(r), " (your hand pulls back from this)" if rr else ""))
            s = "you held the %s; a menu opened beside it" % n
            if rows:
                s += ": " + ", ".join(rows)
            return s[:240]
        return "you %s the %s and it opened in front" % (v, n)
    if verdict == "miss":
        return "you %s the %s and nothing changed" % (v, n)
    if verdict == "unexpected":
        return "you %s the %s; %s" % (v, n, why or "something else happened")
    if verdict == "unverified":
        return "you %s the %s; your eyes could not check what happened" % (v, n)
    if verdict == "not_hers":
        return "you %s the %s, but another hand was busy at the same moment, so it does not count" % (v, n)
    if verdict == "withdrawn" and (fl or {}).get("kind") == "not_mine":
        if (fl or {}).get("rule") == _FULLSCREEN_RULE and _ef("touch_tell"):   # eyes_fix F10: the rule read the WINDOW in front
            fw = (fl or {}).get("front")                                        # (C10 L86946), not her toy: name the window
            return ("the window in front of your screen%s is someone else's (Ace's) -- not the %s; your finger did not touch it"
                    % ((" (%s)" % fw) if fw else "", n))
        if (fl or {}).get("phase") == "aim":
            return "you looked at the %s; it is someone else's (Ace's), and your hand stayed with you" % n
        return "your finger came near the %s; it is someone else's (Ace's), and your hand drifted back" % n
    if verdict == "withdrawn":
        if again:
            return "you reached for the %s again and pulled back again" % n
        if (fl or {}).get("phase") == "aim":
            return "you looked at the %s and your hand did not go toward it" % n
        if (fl or {}).get("phase") == "guard":
            return "your finger was on the %s and came back without pressing" % n
        return "you reached for the %s and your finger pulled back before touching it" % n
    if verdict == "vetoed":
        return "you were about to %s the %s; Ace's hand moved; you waited" % (verb.replace("_", " "), n)
    if verdict == "not_yet":
        return "you wanted to %s the %s; %s" % (verb.replace("_", " "), n, why or "that is not for touching yet")
    if verdict == "covered":
        return "you wanted to %s the %s; your strip was over it; you waited" % (verb.replace("_", " "), n)
    if verdict == "unfelt":
        return "you did not touch the %s" % n
    return "you wanted to %s the %s; %s" % (verb.replace("_", " "), n, why or "it did not happen")


def finger_clause(now: Optional[float] = None) -> str:
    """For body_feel's line: a flinch ONLY if her brainstem felt it (reflex_link.last_felt under 30 s old); else the last
    press as magnitudes and outcome; '' when nothing happened in 30 s. No emotion name, no rule text."""
    now = OS.CLOCK.time() if now is None else float(now)
    try:
        if RL is not None:
            lf = RL.snapshot().get("last_felt")
            if lf and 0.0 <= now - float(lf.get("felt_t") or 0.0) <= FINGER_CLAUSE_S:
                w = flinch_words(lf)
                return " " + w[0].upper() + w[1:] + "."
        ts = OS.trip_state(now)                        # perma (10-21): a stuck trip that cleared itself is told, never hidden
        lc = ts.get("last_clear_t")
        if lc is not None and 0.0 <= now - float(lc) <= FINGER_CLAUSE_S:
            n = int(ts.get("trips_hour") or 0)
            return " Your fingertip was held and is free again (held %d time%s in the last hour)." % (n, "" if n == 1 else "s")
        t = _ts()
        with t["mu"]:
            last = dict(t["last"]) if t["last"] else None
        if last and 0.0 <= now - float(last["t"]) <= FINGER_CLAUSE_S:
            g = last["gesture"]
            act = {"tap": "pressed", "double_tap": "pressed twice", "hold": "held %.1f s" % float(last.get("held_s") or 0.0)}[g]
            ans = "it answered" if last.get("verdict") == "hit" else "nothing answered"
            return " Your fingertip %s; %s." % (act, ans)
    except Exception:
        return ""
    return ""


# ── body: the reach, the press, the lift, the withdrawal (owner 'sour'; success True always) ─────────────────────────────
def _pub(fairy):
    try:
        from infrastructure import efference_copy as _ec
        return _ec.publisher_for(fairy)
    except Exception:
        return None


def _rest_xy() -> Optional[List[int]]:
    try:
        from infrastructure import efference_copy as _ec
        r = _ec.sampler().rest_now()
        return list(r["xy"]) if r else None
    except Exception:
        return None


def _withdraw_action() -> str:
    """Decision E3 (Ace: yes): a flinch snaps back on the phantom bridge's own additive 'withdraw' signature, which ships in the
    SAME install set (motor_phantom_bridge.py; the installer is all-or-nothing). Were the key ever missing, the bridge gives
    an unknown action generic engagement -- and with success True nothing is rewritten (MPB:204-217)."""
    return "withdraw"


def _path(a, b, frac0: float, frac1: float, hz: float, secs: float) -> List[Tuple[float, int, int]]:
    n = max(1, int(round(hz * secs)))
    out = []
    for i in range(1, n + 1):
        f = frac0 + (frac1 - frac0) * i / float(n)
        out.append((secs * i / float(n), int(round(a[0] + (b[0] - a[0]) * f)), int(round(a[1] + (b[1] - a[1]) * f))))
    return out


def _arm(pub, pts, action: str, eid: str, extra: Optional[Dict] = None) -> None:
    if pub is None:
        return
    t0 = OS.CLOCK.time()
    for dt, x, y in pts:
        p = {"action": action, "type": "mouse_move", "owner": "sour", "source": "touch", "device": "finger", "x": x, "y": y,
             "success": True, "t": t0 + dt, "timestamp": t0 + dt, "efference_id": eid}
        if extra:
            p.update(extra)
        try:
            pub("motor.mouse_move", p)
        except Exception:
            pass
        OS.CLOCK.sleep(1.0 / REACH_HZ)


def _marker(x: int, y: int, secs: float) -> None:
    try:
        tmp = MARKER_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"x": int(x) + 2, "y": int(y) + 2, "until": OS.CLOCK.time() + secs, "pid": os.getpid()}, f)
        for _ in range(8):
            try:
                os.replace(tmp, MARKER_FILE)
                break
            except PermissionError:
                OS.CLOCK.sleep(0.05)
        _spawn_marker()
    except Exception:
        pass


def _spawn_marker() -> None:
    """One fingertip-marker process (its own window styles: click-through, no-activate). Cell T0 replaces this."""
    st = _ts()
    with st["mu"]:
        p = st.get("marker_proc")
        if p is not None and p.poll() is None:
            return
        import subprocess
        exe = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        if not os.path.exists(exe):
            exe = sys.executable
        st["marker_proc"] = subprocess.Popen([exe, MARKER_SCRIPT, MARKER_FILE, str(os.getpid())],
                                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), close_fds=True)


def _strip(it, text: str, secs: float) -> None:
    try:
        if it is not None and hasattr(it, "overlay_show"):
            it.overlay_show(text, secs)
    except Exception:
        pass


def _surprise(text: str, key: str, weight: float) -> None:
    try:
        from infrastructure import surprise as _sp
        _sp.push("hand", text, key=key, weight=weight)
    except Exception:
        pass


# ── the flinch: enforced already (no call was made); now it is FELT, or touch latches ────────────────────────────────────
def withdraw(fl: Dict, verb: str, name: str, fairy=None, it=None, point=None, rest=None, eid: str = "",
             quiet: bool = False) -> Dict:
    """fl: touch_lists.flinch_dict(...) with phase / reach_frac / stop_px. Returns the outcome (verdict 'withdrawn')."""
    now = OS.CLOCK.time()
    fl = dict(fl)
    fl.setdefault("t", now)
    key = "%s|%s" % (verb, str(name).lower())
    t = _ts()
    throttled = False
    with t["mu"]:
        tl = [x for x in t["flinches"].get(key, []) if now - x < REPEAT_WIN_S]
        again = len(tl) >= 1
        tl.append(now)
        t["flinches"][key] = tl
        first_cls = fl.get("cls") not in t["first_cls"]
        t["first_cls"].add(fl.get("cls"))
        if fl.get("phase") == "aim":                   # skeptic m4: an inhibited reach jolts her at most once per AIM_REOFFER_S
            if now - float(t.get("aim_offer_t") or -1e18) < AIM_REOFFER_S:
                throttled = True
            else:
                t["aim_offer_t"] = now
    fid = None
    if not throttled:
        fid = RL.offer(fl) if RL is not None else None
        if fid is None:
            OS.latch("unfelt", "the reflex link was full or missing: a flinch could not reach her brainstem")
    pub = _pub(fairy)
    not_mine = (fl.get("kind") or TL.KIND.get(fl.get("cls"))) == "not_mine"
    if fl.get("phase") in ("land", "guard", "tidy") and point is not None:
        start = point if fl.get("phase") != "land" or not fl.get("from_xy") else fl.get("from_xy")
        back_to = rest or start
        pts = _path(start, back_to, 0.0, 1.0, REACH_HZ, float(fl.get("retract_s") or 0.2))
        # E3: a flinch snaps back on the bridge's own 'withdraw' signature; NOT-MINE (E2) glides back on today's move_mouse.
        # success: True always (one success False on a known key rewrites the shared signature for good, MPB:212-217)
        _arm(pub, pts, "move_mouse" if not_mine else _withdraw_action(), eid,
             {"source": "touch_reflex", "withdraw": not not_mine, "cls": fl.get("cls"), "kind": fl.get("kind")})
    words = ("Sour: '%s' is yours; her hand came back" if not_mine else "Sour pulled back from '%s'") % _q(name)
    if quiet:                                          # set 1e: a cued deed opens no window of hers (her console says it)
        _say(words)
    else:
        _strip(it, words, FLINCH_STRIP_S)
    felt = False
    t_end = OS.CLOCK.time() + FELT_WAIT_S
    cut_short = False
    while fid is not None:
        if RL.felt_through(fid):
            felt = True
            break
        if OS.CLOCK.time() >= t_end:
            break
        if OS.ace_waiting_live():
            cut_short = True
            with t["mu"]:
                t["pending_felt"].append((fid, t_end))
            break
        OS.CLOCK.sleep(POLL_WAIT_S)
    if fid is not None and not felt and not cut_short:
        OS.latch("unfelt", "flinch %s was not felt by her brainstem within %.0f s" % (fid, FELT_WAIT_S))
    numbers = {k: fl.get(k) for k in ("cls", "phase", "intensity", "retract_s", "stop_px", "reach_frac")}
    numbers.update(felt=felt, id=fid, again=again, rule=fl.get("rule"), throttled=throttled)
    _bump("withdrawn_" + str(fl.get("phase")))
    if felt and first_cls:
        _surprise(flinch_words(fl), "flinch:%s" % fl.get("cls"), 0.5)
    out = {"ok": None, "count": False, "no_chord": True, "ms": int(1000 * (OS.CLOCK.time() - now)),
           "summary": (tell(verb, name, "withdrawn", fl=fl, again=again) if (felt or throttled)   # m4: a throttled AIM is told
                       else tell(verb, name, "unfelt")),                                       # as the inhibited reach it was
           "touch": {"verdict": "withdrawn", "gesture": verb, "item": _q(name), "flinch": numbers}}
    if fl.get("phase") in ("land", "guard") and point is not None:
        out["target"] = list(point)
    if cut_short:
        out["deferred"] = True
    return out


# ── the deed ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
def _ef(key: str) -> bool:
    """eyes_fix_1009: one key of Ace's eyes switch (state/eyes_fix.json, infrastructure/eyes_fix.py); OFF on any doubt (the
    module absent, the file absent or malformed) -- then every line marked eyes_fix runs today's path."""
    try:
        from infrastructure import eyes_fix as _efm
        return _efm.on(key)
    except Exception:
        return False


_FULLSCREEN_RULE = "a full-screen window is in front"   # touch_lists._no_no's words for that rule (test T10 holds them equal)


def _front_of(f: Dict, fl) -> Dict:
    """eyes_fix F10 'touch_tell': the front window the full-screen rule read (its exe, else its class), to name in the telling."""
    try:
        if getattr(fl, "rule", None) == _FULLSCREEN_RULE and _ef("touch_tell"):
            nm = str((f or {}).get("fg_exe") or (f or {}).get("fg_class") or "")[:40]
            return {"front": nm} if nm else {}
    except Exception:
        pass
    return {}


def _deferred(verb, name, verdict, why="", **touch) -> Dict:
    d = {"ok": False, "count": False, "deferred": True, "no_chord": True, "ms": 0,
         "summary": tell(verb, name, verdict, why=why),
         "touch": dict({"verdict": "deferred", "reason": verdict, "why": str(why)[:120], "gesture": verb, "item": _q(name)},
                       **touch)}
    if _who_on() or _ef("touch_tell"):             # set1c (who touched) / eyes_fix F10 (touch_tell): a touch that did not happen is told as not having happened
        d["summary"] = d["summary"] + "; your finger did not touch it"
    return d


def _lane() -> str:
    hd = sys.modules.get("infrastructure.hand_door")
    try:
        return getattr(hd._CTX, "lane", None) or "direct"
    except Exception:
        return "direct"


def _door_tempo(name: str, point) -> Optional[str]:
    """The door's place tempo (hand_door.hook 'pre_actuate') with hand=None: a tap where the hand rests means something, so
    the 40 px no-op is skipped for touch (DESIGN 9); the refractory and the loop guard stay. None = go on."""
    hd = sys.modules.get("infrastructure.hand_door")
    if hd is None:
        return None
    try:
        r = hd.hook("pre_actuate", obj=name, target=list(point), hand=None, idle=None)
    except Exception:
        return None
    if r and r.get("deferred"):
        return "your hand had only just moved"
    return None


def _nonce() -> Optional[str]:
    hd = sys.modules.get("infrastructure.hand_door")
    try:
        return hd.deed_nonce()
    except Exception:
        return None


def _resolve(name: str, pr: Optional[Dict]) -> Optional[Dict]:
    """The Playroom item by its exact name (case-insensitive), from the Playroom's OWN state file (rects in physical px)."""
    if not pr:
        return None
    for t in pr.get("toys") or []:
        if str(t.get("name", "")).casefold() == str(name).casefold():
            r = t.get("rect")
            if not r or len(r) != 4:
                return None
            return {"name": t.get("name"), "rect": [int(v) for v in r],
                    "point": [int((r[0] + r[2]) // 2), int((r[1] + r[3]) // 2)]}
    return None


def _menu_now(pr_pid: Optional[int], before: set) -> Optional[Dict]:
    ts = OS.tops()
    if ts is None:
        return None
    for w in ts:
        if w["hwnd"] not in before and w["class"] == OS.PLAYROOM_MENU and w["pid"] == pr_pid:
            return w
    return None


def _write_ctl(d: Dict) -> None:
    """Her side may write two things only to the Playroom's control file: cancel_menu and hold_menu_until."""
    clean = {k: v for k, v in d.items() if k in ("cancel_menu", "hold_menu_until")}
    clean["t"] = OS.CLOCK.time()
    try:
        tmp = PLAYROOM_CTL + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(clean, f)
        for _ in range(8):
            try:
                os.replace(tmp, PLAYROOM_CTL)
                return
            except PermissionError:
                OS.CLOCK.sleep(0.05)
    except Exception:
        pass


# ── set 1e (10-13): her reach shown INSIDE her Playroom (probe F9c 10-13: her strip and marker windows took Ace's focus) ─────
def _cue_route(verb: str, kind: str, pr: Optional[Dict]) -> Optional[Dict]:
    """The channel her reach is shown over this deed (touch_os.cue_route), or None: then set 1d's marker and strip, unchanged."""
    try:
        info, _why = OS.cue_route(kind, verb, pr)
    except Exception:
        return None
    _bump("cue_route" if info is not None else "cue_none")
    return info


def _show_reach(it, txt: str, name: str, cue: Optional[Dict]) -> str:
    """Her announce's first act. No cue: set 1d's strip (txt), unchanged. A cue: 'cue <toy> CUE_MS' to her Playroom, which draws
    it INSIDE its own window -- no window of hers opens; it must say it shows it, or she does not press. -> '' or 'cue:<why>'."""
    if cue is None:
        _strip(it, txt, ANNOUNCE_S + 1.0)
        return ""
    r = OS.cue_show(cue, name, CUE_MS)
    if not r.get("ok") and r.get("sent"):              # it left her side but was not confirmed: it may show -- take it away
        _cue_cancel(cue, name)
    return "" if r.get("ok") else "cue:" + str(r.get("why") or "no clear answer")


def _cue_cancel(cue: Optional[Dict], name: str) -> None:
    if cue is not None:
        try:
            OS.cue_cancel(cue, name)
        except Exception:
            pass


def _unshow(cue: Optional[Dict], name: str, why: str) -> Tuple[None, str]:
    """An announce that ends without her press: her Playroom stops showing her reach (best effort)."""
    _cue_cancel(cue, name)
    return None, why


def _focus_moved(par: Dict) -> bool:
    """The focus is READABLE and is not the one read before anything of hers showed (set1c's focus0)."""
    f = OS.focus_now()
    return bool(f) and bool(f.get("ok")) and not OS.same_focus(f, par.get("focus0"))


def _his_click_brought_it(room: Dict, par: Dict, since: float) -> bool:
    """set 1e review (verify_tests F1): did ACE'S CLICK bring her Playroom to the front? -- the Playroom she aimed in is in front
    AND its own log holds a click of his (CUE_CLICK_EVS) since her guard read his room. A cue that takes the focus leaves no
    click there; keys and moves that land in the Playroom after a focus move are its consequence, never its cause. Windows
    moves the focus a moment before the Playroom logs the click, so his room is read again every 50 ms for up to CUE_HAND_WAIT_S
    (nothing of hers moves meanwhile: she is already not pressing). Read-only; any sense that cannot say -> False (the latch)."""
    t_end = OS.CLOCK.time() + CUE_HAND_WAIT_S
    while True:
        if room.get("ok") and room.get("fg_room") is True and room.get("hwnd") == par["room"]["hwnd"]:
            rows = OS.playroom_rows(since)
            if rows and any(OS.room_kind(r) in CUE_CLICK_EVS for r in rows):
                return True
        if OS.CLOCK.time() >= t_end:
            return False
        OS.CLOCK.sleep(POLL_INPUT_S)
        room = OS.room_state()


def _playroom_hand(res: Dict) -> bool:
    """set 1e review (verify_safety F3): her Playroom refused her press over its channel because ACE's hand was in it during her
    cue (its own words, exact): nothing happened ('not_done'), and it is his veto."""
    ch = res.get("channel") if isinstance(res.get("channel"), dict) else {}
    return ch.get("outcome") == "not_done" and ch.get("why") in PLAYROOM_HAND_WHYS


def _announce(it, verb: str, name: str, then: Optional[str], cue: Optional[Dict] = None) -> Tuple[Optional[Dict], str]:
    """Ace's veto: the strip shows the touch 1.5 s ahead; both input channels every 50 ms and his waiting message every
    250 ms. Returns (announce snapshot, '') or (None, why) on a cancel. set 1e: a cued deed shows her reach INSIDE her Playroom
    instead of the strip (_show_reach); a cancel takes it away (_unshow); his veto is the same."""
    ch = OS.channels()
    if not ch["ok"]:
        return None, "off:" + ch["why"]
    snap = {"phys_n": ch["phys_n"], "lii": ch["lii"], "t": OS.CLOCK.time()}
    txt = ("Sour: %s '%s', then '%s', in 1.5 s" % (verb, _q(name), _q(then))) if then else ("Sour: %s '%s' in 1.5 s" % (verb, _q(name)))
    shown = _show_reach(it, txt, name, cue)
    if shown:
        return None, shown
    t0 = OS.CLOCK.time()
    next_wait = t0
    while OS.CLOCK.time() - t0 < ANNOUNCE_S:
        c = OS.channels()
        if not c["ok"]:
            return _unshow(cue, name, "off:" + c["why"])
        if c["phys_n"] != snap["phys_n"] or c["lii"] != snap["lii"]:
            return _unshow(cue, name, "ace_veto")
        if OS.CLOCK.time() >= next_wait:
            if OS.ace_waiting_live():
                return _unshow(cue, name, "ace_veto")
            next_wait += POLL_WAIT_S
        OS.CLOCK.sleep(POLL_INPUT_S)
    return snap, ""


def execute(intent: Dict, fairy=None, it=None) -> Optional[Dict]:
    verb = intent.get("verb")
    obj = str(intent.get("object") or "")
    t_start = OS.CLOCK.time()
    lane = _lane()
    name, then = parse_target(obj, verb)
    try:
        out = _execute(verb, name, then, fairy, it, lane, t_start)
    except Exception as e:
        _say("execute raised %s: %s" % (type(e).__name__, str(e)[:100]))
        out = _deferred(verb, name, "failed", "something in your fingertip did not work")
        out["touch"]["verdict"] = "unverified"
    if out is not None:
        out["lane"] = lane
        out.setdefault("ms", int(1000 * (OS.CLOCK.time() - t_start)))
    return out


def _execute(verb, name, then, fairy, it, lane, t_start, parked=False) -> Optional[Dict]:
    sw = OS.read_switch()
    if not sw["on"] or verb not in VERBS:
        return _deferred(verb, name, "off", "touch is off")
    stage = sw["data"].get("stage")
    kind = _kind_of(stage)
    ok, why = OS.ready()
    if not ok:
        return _deferred(verb, name, "off", why)
    if _revoked(OS.CLOCK.time()):
        return _deferred(verb, name, "ace_first", "Ace took the hands back a little while ago")
    a_ok, a_why = (False, "missing") if RL is None else RL.alive(OS.CLOCK.time())
    if not a_ok:
        if a_why in ("two_beaters", "beater_changed"):   # skeptic S6: a changed brainstem latches here too, not only at a press
            OS.latch("beaters", "the beating brainstem changed (%s)" % a_why)
        if OS.knobs(sw).get("cue") is True:            # set 1e review (verify F1/F9): under the cue switch no window of hers
            _say("Sour's touch waits: her reflex is not awake")   # opens -- her console says it (a strip took his focus, F9c)
        else:
            _strip(it, "Sour's touch waits: her reflex is not awake", 3.0)
        return None                                    # nothing is told to her; the strip tells Ace (DESIGN 3d)
    pr, pwhy = OS.verify_playroom() if kind == "playroom" else (None, "not the Playroom stage")
    mons, bars = OS.screen_geometry()
    tgt = _resolve(name, pr)
    cue = _cue_route(verb, kind, pr)                   # set 1e: her reach shown INSIDE her Playroom: no window of hers this deed
    # 1 AIM -- the named item (and Y of a compound hold): a no-no is an INHIBITED reach, no arm motion. Deny before allow:
    # it is checked before every NOT-YET answer below, so a no-no is always felt as her flinch (DESIGN 6a, 7d)
    actx = {"monitors": mons, "taskbars": bars, "point": tgt["point"] if tgt else None}
    for nm in [name] + ([then] if then else []):
        fl = TL.no_no(item={"name": nm}, gesture=verb, phase="aim", ctx=actx if nm == name else {})
        if fl is not None:
            return withdraw(TL.flinch_dict(fl, reach_frac=0.0, stop_px=None, t=OS.CLOCK.time()), verb, nm, fairy, it,
                            quiet=cue is not None)
    if kind != "playroom":
        return _deferred(verb, name, "not_yet", "the desktop is not for touching yet")      # set 2
    if verb in OFF_GESTURES:
        return _deferred(verb, name, "not_yet", "that is not for touching that way yet")
    if then and not MENU_PICKS_ON:
        return _deferred(verb, name, "not_yet", "picking from a menu is not for touching yet")
    if pr is None:
        return _deferred(verb, name, "not_yet", "your Playroom is not open (%s)" % pwhy)
    if tgt is None:
        return _deferred(verb, name, "not_yet", "there is nothing called that in your Playroom")
    # Ace first BEFORE anything shows (skeptic S2; DESIGN 8: "at the door, the gate, the press"): while his hand was busy inside
    # the stage's idle floor there is no arm motion, no marker on his screen, no strip and no UIA read. The guard checks again.
    ch = OS.channels()
    if not ch["ok"]:
        return _deferred(verb, name, "off", ch["why"])
    floor = OS._idle_floor({"kind": kind, "gesture": verb}, sw["data"])
    idle_ms = OS._wrap_ms(ch["tick"], ch["lii"])
    par = None
    busy = _hands(verb, kind, sw, pr, floor, idle_ms, parked, name, cue=cue)   # set1c: None = set 1's rule below, unchanged
    if busy is not None:
        if busy.get("outcome") is not None:
            return busy["outcome"]                     # parked and his hands moved again: told plainly, never pressed
        if busy.get("rerun"):                          # parked until his hands were still: EVERYTHING once more, never retried
            return _after_park(verb, name, then, fairy, it, lane)
        par, idle_ms = busy.get("parallel"), busy["idle_ms"]   # parallel play: the idle that counts is HIS ROOM's
    if idle_ms < floor * 1000.0:
        return _deferred(verb, name, "ace_first", "Ace's hand was busy %.1f s ago; you waited" % (idle_ms / 1000.0),
                         reason="ace_first")
    eid = "touch-%d" % int(OS.CLOCK.time() * 1000)
    pub = _pub(fairy)
    rest = _rest_xy() or OS.rest_cursor() or tgt["point"]
    point = tgt["point"]
    tempo = _door_tempo(name, point)
    if tempo:
        return _deferred(verb, name, "tempo", tempo)
    # 2 REACH (80 %)
    if pub is not None:
        try:
            pub("phantom.pre_envision", {"action": "click", "owner": "sour", "source": "touch", "device": "finger",
                                         "gesture": verb, "target": {"x": point[0], "y": point[1]}, "reach_from": rest,
                                         "efference_id": eid, "t": OS.CLOCK.time()})
        except Exception:
            pass
    if cue is None:                                    # set 1e: a cued deed has no marker window (her Playroom shows her reach)
        _marker(point[0], point[1], REACH_S + ANNOUNCE_S + 3.0)
    _arm(pub, _path(rest, point, 0.0, LAND_AT, REACH_HZ, REACH_S * LAND_AT), "move_mouse", eid)
    at = [int(round(rest[0] + (point[0] - rest[0]) * LAND_AT)), int(round(rest[1] + (point[1] - rest[1]) * LAND_AT))]
    # 3 LAND -- Win32 first (no UIA on a no-no window)
    f = OS.facts_at(point)
    if OS.covered(f):
        return _deferred(verb, name, "covered", reason="covered")
    fl = OS.no_no_at(f, {"name": name, "rect": tgt["rect"]}, verb, "land", pr.get("pid"))
    if fl is not None:
        d = TL.flinch_dict(fl, reach_frac=LAND_AT, stop_px=int(round(math.hypot(point[0] - at[0], point[1] - at[1]))),
                           t=OS.CLOCK.time(), from_xy=at, **_front_of(f, fl))   # eyes_fix F10: + the front window's name
        return withdraw(d, verb, name, fairy, it, point=at, rest=rest, eid=eid, quiet=cue is not None)
    _arm(pub, _path(rest, point, LAND_AT, 1.0, REACH_HZ, REACH_S * (1.0 - LAND_AT)), "move_mouse", eid)
    rd = OS.read_at(point, verb)
    if rd.get("flinch"):
        d = dict(rd["flinch"], reach_frac=1.0, stop_px=0, t=OS.CLOCK.time())
        return withdraw(d, verb, name, fairy, it, point=point, rest=rest, eid=eid, quiet=cue is not None)
    if not rd.get("ok"):
        return _deferred(verb, name, "not_yet", rd.get("why") or "it could not be read")
    el = rd["el"]
    f = rd.get("facts") or f
    if el.get("pid") != f.get("pid"):
        return _miss_outcome(verb, name, "another window lay over it", point)
    allow, awhy = OS.load_allow(OS.read_switch())
    if allow is None:
        return _deferred(verb, name, "off", awhy)
    ny = OS.not_yet(f, el, verb, allow, pr, False, _layout_names())
    if ny:
        return _deferred(verb, name, "not_yet", ny)
    if str(el.get("name")) != str(tgt["name"]) or any(abs(a - b) > OS.RECT_TOL_PX for a, b in zip(el.get("rect") or [], tgt["rect"])):
        return _miss_outcome(verb, name, "the thing under your finger was not it", point)
    # 4 ANNOUNCE = Ace's veto
    before_tops = OS.tops()
    snap, vwhy = (_announce_parallel(it, verb, name, then, par, cue=cue) if par
                  else _announce(it, verb, name, then, cue=cue))               # set 1e: the cue, when the deed is cued
    if snap is None:
        if vwhy == "focus":
            return _focus_outcome(verb, name)          # set1c: the FOCUS LATCH tripped before her press; nothing was pressed
        if vwhy == "ace_veto":
            return _deferred(verb, name, "vetoed", "Ace's hand moved", reason="ace_veto")
        if vwhy.startswith("cue:"):                    # set 1e: her Playroom did not confirm it shows her reach: no press
            if vwhy[4:] in PLAYROOM_HAND_WHYS:         # set 1e review (verify F3): it refused because ACE's hand was in it
                return _deferred(verb, name, "vetoed", "Ace's hand moved", reason="ace_veto")
            return _deferred(verb, name, "cue", "your Playroom could not show your reach (%s), so your finger waited"
                             % vwhy[4:80], reason="cue")
        return _deferred(verb, name, "off", vwhy[4:])
    if OS.CLOCK.time() - t_start > DEED_CAP_S:
        return _deferred(verb, name, "failed", "the moment passed")
    # 5-6 PRESS
    pub_click = {"owner": "sour", "device": "finger", "action": "click", "gesture": verb, "x": point[0], "y": point[1],
                 "efference_id": eid}
    hb0 = OS.heartbeat_read(pr)
    t_hb0 = OS.CLOCK.time()
    req = {"op": "press", "nonce": _nonce(), "gesture": verb, "call": CALL_OF.get(verb), "point": list(point),
           "stage": stage, "lane": lane, "kind": kind, "aim": dict(el, root=f.get("root")), "then_item": then,
           "announce": snap, "switch_key": OS.read_switch().get("key"), "outstanding_ok": _outstanding_ok(kind),
           "menu_ok": False, "layout_names": _layout_names()}
    if cue is not None:                                # set 1e: her reach was shown inside her Playroom: its channel only
        req["cued"] = True
    if par:                                            # set1c parallel play: his room is the veto; the focus latch brackets the call
        req.update(parallel=True, focus0=par["focus0"], room=par["room"], menu=par.get("menu"))
    res = OS.press(req)
    if cue is not None and not res.get("pressed") and (res.get("channel") or {}).get("sent") is not True:
        _cue_cancel(cue, name)                         # set 1e: nothing left her side: her Playroom stops showing her reach
    if not res.get("pressed"):
        k = res.get("kind")
        if res.get("reason") == "focus_latch":         # set1c: the focus moved before her press: nothing was pressed
            return _focus_outcome(verb, name)
        if res.get("reason") == "stuck" and _who_on():  # set1c (verify W3): a HELD press may still have touched: never 'did not'
            return _stuck_outcome(verb, name)
        if res.get("reason") == "channel_unsure":       # set 1d: her Playroom got it and gave no clear answer: never 'did not'
            return _unsure_outcome(verb, name)
        if k == "withdrawn" and res.get("flinch"):
            return withdraw(res["flinch"], verb, name, fairy, it, point=point, rest=rest, eid=eid, quiet=cue is not None)
        if res.get("reason") == "ace_veto" or (cue is not None and _playroom_hand(res)):   # set 1e review (verify F3): or her
            return _deferred(verb, name, "vetoed", "Ace's hand moved", reason="ace_veto")   # Playroom refused it for his hand
        if k == "not_yet":
            return _deferred(verb, name, "not_yet", res.get("why"))
        if k == "moved":
            return _deferred(verb, name, "moved", "it moved before your finger got there")
        return _deferred(verb, name, k or "failed", res.get("why"))
    t_press = OS.CLOCK.time()
    if pub is not None:
        try:
            pub("motor.mouse_click", dict(pub_click, t=t_press, timestamp=t_press, success=True))
        except Exception:
            pass
    # 7 WATCH
    menu = None
    sel_after = None
    if verb == "hold":
        bset = {w["hwnd"] for w in (before_tops or [])}
        t_w = OS.CLOCK.time()
        while OS.CLOCK.time() - t_w < WATCH_S:
            menu = OS.menu_panel(pr) if pr.get("set1d") is True else _menu_now(pr.get("pid"), bset)   # set 1d: its panel, also
            #                                                                    over the strict UIA fallback (verify S3)
            if menu is not None:
                break
            OS.CLOCK.sleep(0.1)
    else:
        OS.CLOCK.sleep(WATCH_S)
    held_s = (OS.CLOCK.time() - t_press) if verb == "hold" else 0.0
    rest_s = HEARTBEAT_GAP_S - (OS.CLOCK.time() - t_hb0)      # the heartbeat changes once a second: read it again only after
    if rest_s > 0:                                            # >= 1.05 s, or a live sense reads as dead (a menu can come fast)
        OS.CLOCK.sleep(rest_s)
    after_tops = OS.tops()
    hb1 = OS.heartbeat_read(pr)
    if hb0 is not None and hb0 == hb1 and OS.CLOCK.time() - t_hb0 >= HEARTBEAT_ALIAS_S:   # skeptic m11: a 4 s pair can alias;
        hb0 = hb1                                                                       # read a fresh pair 1.05 s apart
        OS.CLOCK.sleep(HEARTBEAT_GAP_S)
        hb1 = OS.heartbeat_read(pr)
    if verb == "tap":
        ra = OS.read_at(point, verb)
        sel_after = (ra.get("el") or {}).get("selected") if ra.get("ok") else None
    alive = before_tops is not None and after_tops is not None and hb0 is not None and hb1 is not None and hb0 != hb1
    bset = {w["hwnd"] for w in (before_tops or [])}
    new = [dict(w, descends=False) for w in (after_tops or []) if w["hwnd"] not in bset]
    menu_rows = []
    mobs = None
    if menu is not None:
        prn, _w = OS.verify_playroom()
        m = (prn or {}).get("menu") or {}
        menu_rows = [str(r.get("name")) for r in m.get("rows") or []]
        mr = menu.get("rect") or [0, 0, 0, 0]
        near = math.hypot((mr[0] + mr[2]) / 2.0 - point[0], (mr[1] + mr[3]) / 2.0 - point[1]) if menu.get("rect") else 9999.0
        mobs = {"hwnd": menu["hwnd"], "pid": menu["pid"], "class": menu["class"], "near_px": min(near, math.hypot(mr[0] - point[0], mr[1] - point[1])),
                "for_item": m.get("for")}
    obs = {"violation": res.get("violation"), "ace_input": bool(res.get("ace_input")), "senses_alive": alive,
           "new_tops": new, "playroom_pid": pr.get("pid"), "selected_before": el.get("selected"),
           "selected_after": sel_after, "menu": mobs, "expect_item": tgt["name"]}
    verdict, why = judge(verb, obs)
    # lift
    t_lift = OS.CLOCK.time()
    if pub is not None:
        try:
            pub("motor.mouse_click", dict(pub_click, gesture="release", t=t_lift, timestamp=t_lift, success=True))
        except Exception:
            pass
    try:
        from infrastructure import efference_copy as _ec
        if hasattr(_ec, "let_go_at"):
            _ec.let_go_at(point, t_lift, "touch")
    except Exception:
        pass
    # 11 TIDY: a menu she only looked at goes away through the Playroom's own control file
    if menu is not None:
        _write_ctl({"cancel_menu": menu["hwnd"]})
    # 10 RECORD
    _book(verb, name, kind, verdict, held_s, t_press, watched=bool(sw["data"].get("watched")),
          habit=not res.get("focus_changed"))          # set1c (verify S3): a press that moved the focus builds no habit
    if verdict in ("miss", "unexpected"):
        _surprise(tell(verb, name, verdict, why=why), "touch", 0.5)
    summ = tell(verb, name, verdict, why=why, menu_rows=menu_rows)
    if res.get("focus_changed"):                       # set1c: she pressed, and the focus moved across it: a 'not mine' moment
        summ = summ + "; then " + NOT_MINE_WORDS
        _not_mine_moment()
    ok = {"hit": True, "miss": False, "unexpected": False, "violation": False}.get(verdict)
    out = {"ok": ok, "summary": summ, "target": list(point), "touch": {
        "verdict": verdict, "why": why, "gesture": verb, "item": _q(name), "call": res.get("call"), "held_s": round(held_s, 2),
        "sentinel": res.get("sentinel"), "selected": [el.get("selected"), sel_after], "menu_rows": menu_rows[:8],
        "senses_alive": alive}}
    if par:
        out["touch"]["parallel"] = True                # set1c: played while Ace's hands were busy elsewhere
    if res.get("focus_changed"):                       # set1c (verify S3): a press that moved the focus is no clean deed
        out["count"] = False
    if verdict in ("unverified", "not_hers"):
        out["count"] = False
        out["ok"] = None
    if verdict == "violation":
        out["no_chord"] = True
        habit_note(habit_key(verb, "ListItem", kind, "toy"), False, t_press, violation=True)
    return out


# ── set1c (10-09): parallel play, park, the focus latch, who touched ──────────────────────────────────────────────────────
def _who_on() -> bool:
    try:
        return bool(OS.knobs().get("who"))
    except Exception:
        return False


def _hands(verb, kind, sw, pr, floor, idle_ms, parked, name, cue=None) -> Optional[Dict]:
    """Before anything of hers shows (no arm motion, no marker, no strip). None = set 1's rule decides, unchanged.
    PARALLEL PLAY (the switch's 'parallel', after probe F9): his hands ELSEWHERE do not hold her back; only HIS ROOM does --
      the Playroom in front, his cursor over it, a reply pending, or his input in the Playroom's own log inside its floor.
      The focus is read HERE, before the marker and the strip, so the FOCUS LATCH brackets everything of hers that shows.
    PARK (the switch's 'park_s', the strict rule): his hand was busy inside the floor -> wait out the rest of the floor if
      that is <= park_s, polling every 50 ms; ANY new input cancels (told plainly, never retried); else everything runs again
      once (_after_park). The hand_door claim is held and the council loop waits through a park (BUILD.md)."""
    kn = OS.knobs(sw)
    if not kn.get("on") or kind != "playroom" or pr is None:
        return None
    if verb in kn["parallel"] and not OS.parallel_latched(sw.get("key")) and cue is not None:   # set 1e (P1): cued only
        room = OS.room_state(pr)
        if room.get("ok") and not room.get("in_room") and float(room.get("idle_ms") or 0.0) >= floor * 1000.0:
            f0 = OS.focus_now()
            menu = _menu_projection(verb, name, pr, room) if verb == "hold" else None
            if f0 is not None and f0.get("ok") and (verb != "hold" or menu is not None):
                _bump("parallel_go")
                return {"parallel": {"room": {"hwnd": room["hwnd"], "pid": room["pid"], "rect": list(room["rect"])},
                                     "focus0": f0, "switch_key": sw.get("key"), "menu": menu,
                                     "t_guard": OS.CLOCK.time()},      # set 1e review (verify F1): when her guard read his room
                        "idle_ms": float(room["idle_ms"])}
        _bump("parallel_strict")                       # Ace is in her room (or a sense could not say): set 1's rule decides
    if parked or idle_ms >= floor * 1000.0 or float(kn.get("park_s") or 0.0) <= 0.0:
        return None
    wait_s = floor - idle_ms / 1000.0
    if wait_s > float(kn["park_s"]):
        return None
    return _park(verb, name, wait_s)


def _menu_projection(verb, name, pr, room) -> Optional[Dict]:
    """verify S1: a parallel HOLD opens the Playroom's menu, a TOPMOST popup, at the toy's right edge (set1/playroom/playroom.py
    _open_menu: toy right + 6, toy top, 210 x 28*rows + 8, never clamped). It plays in parallel only when that whole rect lies
    inside the Playroom and the Playroom itself is the root window all over it (touch_os.menu_in_room) -- else a menu of hers
    would drop over one of Ace's windows; then set 1's rule decides (his busy hands defer her). None = not in parallel."""
    tgt = _resolve(name, pr)
    rows = next((len(t.get("menu") or []) for t in _layout().get("toys") or []
                 if str(t.get("name", "")).casefold() == str(name).casefold()), None)
    if tgt is None or not rows:
        return None
    ok, why, rect = OS.menu_in_room(room["hwnd"], room["rect"], tgt["rect"], rows, client=room.get("client"))   # set 1d (S3)
    if not ok:
        _bump("parallel_hold_menu_outside")
        _say("parallel hold '%s' stays strict: %s" % (_q(name), why))
        return None
    return {"toy_rect": list(tgt["rect"]), "rows": int(rows), "rect": rect}


def _stuck_outcome(verb, name) -> Dict:
    """verify W3: the worker held her press past its watchdog. The call may still run late, so it is told as UNKNOWN -- never
    'your finger did not touch it' and never 'you tapped'. Deferred: no ledger deed, no weave, no chord."""
    return {"ok": False, "count": False, "deferred": True, "no_chord": True, "ms": 0,
            "summary": tell(verb, name, "stuck", why="your finger is held; whether it touched cannot be told yet"),
            "touch": {"verdict": "deferred", "reason": "stuck", "why": "your finger is held", "gesture": verb, "item": _q(name)}}


def _unsure_outcome(verb, name) -> Dict:
    """set 1d: her channel carried the touch to her Playroom and no clear answer came back (or its work ran late) -- it may have
    happened, so it is told as UNKNOWN: never 'your finger did not touch it', never 'you tapped'. Deferred: no ledger deed, no
    weave, no chord. Her efference copy has it as not ok, so an effect it caused is 'unsure'."""
    return {"ok": False, "count": False, "deferred": True, "no_chord": True, "ms": 0,
            "summary": tell(verb, name, "unsure", why="your Playroom did not say whether it answered"),
            "touch": {"verdict": "deferred", "reason": "channel_unsure", "why": "your Playroom did not say whether it answered",
                      "gesture": verb, "item": _q(name)}}


def _park(verb, name, wait_s) -> Dict:
    c0 = OS.channels()
    if not c0["ok"]:
        return {"outcome": _deferred(verb, name, "off", c0["why"])}
    _bump("parked")
    _say("park: '%s' waits %.1f s for Ace's hands to be still" % (_q(name), wait_s))
    t_end = OS.CLOCK.time() + wait_s + PARK_MARGIN_S
    next_slow = OS.CLOCK.time()
    while OS.CLOCK.time() < t_end:
        OS.CLOCK.sleep(PARK_POLL_S)
        c = OS.channels()
        if not c["ok"]:
            return {"outcome": _deferred(verb, name, "off", c["why"])}
        if c["phys_n"] != c0["phys_n"] or c["lii"] != c0["lii"]:
            _bump("park_cancelled")
            return {"outcome": _deferred(verb, name, "parked", "you waited for Ace's hands to be still, and they moved again",
                                         reason="park_cancelled")}
        if OS.CLOCK.time() >= next_slow:
            next_slow += POLL_WAIT_S
            if OS.ace_waiting_live() or _revoked(OS.CLOCK.time()) or not OS.ready()[0]:
                _bump("park_cancelled")
                return {"outcome": _deferred(verb, name, "parked", "you waited, and the moment passed", reason="park_cancelled")}
    return {"rerun": True}


def _after_park(verb, name, then, fairy, it, lane) -> Optional[Dict]:
    """After a park: the GATE again (switch, his words, readiness, cooldowns, caps), then the whole deed again from the top
    (the Playroom re-verified, the item re-resolved, the no-no, his hands); parked=True, so it is never parked twice. The deed
    clock starts again here: a park is not part of DEED_CAP_S."""
    obj = name if not then else "%s, then %s" % (name, then)
    g = gate({"verb": verb, "object": obj})
    if g.get("decision") != "allow":
        return _deferred(verb, name, "parked", "you waited; then %s" % g.get("why"), reason="park_regate")
    return _execute(verb, name, then, fairy, it, lane, OS.CLOCK.time(), parked=True)


def _announce_parallel(it, verb: str, name: str, then: Optional[str], par: Dict,
                       cue: Optional[Dict] = None) -> Tuple[Optional[Dict], str]:
    """Ace's veto in PARALLEL PLAY: the same 1.5 s strip, every 50 ms -- his ROOM (in front, cursor over it, a reply pending,
    a new input row in its own log) cancels ('ace_veto'); his hands elsewhere do not; a changed focus cancels AND latches
    ('focus'). Returns (snapshot, '') or (None, why). set 1e: her reach shows INSIDE her Playroom (a cue; parallel play is always
    cued, P1), and his input in her room since the cue was ASKED for counts; any cancel takes the cue away. Set 1e review (verify
    F1): a focus that moved because HIS CLICK brought her Playroom forward is his veto (set 1d's), not the latch."""
    ch = OS.channels()
    if not ch["ok"]:
        return None, "off:" + ch["why"]
    snap = {"phys_n": ch["phys_n"], "lii": ch["lii"], "t": OS.CLOCK.time()}
    txt = ("Sour: %s '%s', then '%s', in 1.5 s" % (verb, _q(name), _q(then))) if then else ("Sour: %s '%s' in 1.5 s" % (verb, _q(name)))
    t_show = OS.CLOCK.time()
    shown = _show_reach(it, txt, name, cue)
    if shown:
        return None, shown
    t0 = OS.CLOCK.time()
    t_in = (t_show - CUE_INPUT_SLACK_S) if cue is not None else t0   # set 1e: his input while her cue was asked counts too
    t_click = (float(par["t_guard"]) if par.get("t_guard") is not None else t_show) - CUE_INPUT_SLACK_S   # review F1: since her guard
    while OS.CLOCK.time() - t0 < ANNOUNCE_S:
        c = OS.channels()
        if not c["ok"]:
            return _unshow(cue, name, "off:" + c["why"])
        room = OS.room_state()
        if (not room.get("ok") or room.get("in_room") or room.get("hwnd") != par["room"]["hwnd"]
                or float(room.get("last_input_t") or 0.0) >= t_in):
            if cue is not None and _focus_moved(par) and not _his_click_brought_it(room, par, t_click):   # set 1e: the latch,
                OS.parallel_latch("the foreground or keyboard focus changed while her cue showed", par.get("switch_key"))   # as below,
                return _unshow(cue, name, "focus")                                                     # unless HIS click did it
            return _unshow(cue, name, "ace_veto")
        f = OS.focus_now()
        if f is None or not f.get("ok"):
            return _unshow(cue, name, "ace_veto")
        if not OS.same_focus(f, par["focus0"]):
            OS.parallel_latch("the foreground or keyboard focus changed during her announce", par.get("switch_key"))
            return _unshow(cue, name, "focus")
        OS.CLOCK.sleep(POLL_INPUT_S)
    return snap, ""


def _not_mine_moment() -> None:
    """A 'not mine' moment: news, never a flinch (no reflex offer, no jolt)."""
    _surprise(NOT_MINE_WORDS, "touch_focus", 0.3)


def _focus_outcome(verb, name) -> Dict:
    d = _deferred(verb, name, "focus", NOT_MINE_WORDS)
    d["touch"]["reason"] = "focus_latch"
    _not_mine_moment()
    return d


def _hand_msg(r: Dict) -> bool:
    ev = str(r.get("ev") or "")
    base = ev[6:] if ev.startswith("QUEUE ") else ev
    return base in OS.HAND_EVS


def attribute(ev: Dict, rows, presses) -> str:
    """WHO TOUCHED one Playroom effect. Pure. 'ace' when the Playroom's own witness shows a REAL hand in her room (the effect
    is marked by_hand, or a button / key message reached it within WHO_HAND_S before it); 'you' ONLY from her efference copy
    -- a touch_os.press that ran and came back ok for that very toy, the effect inside its window [t0 - WHO_PRE_S, t1 +
    WHO_EFF_S]; 'unsure' when a press of hers on that toy lies in that window but did NOT come back ok (a violation, a call that
    raised, a held press that returned late: verify W3) -- it may have been hers, so neither 'you' nor 'not yours'; else
    'unknown'. Never from a visual change alone."""
    toy = str(ev.get("toy") or "").casefold()
    t = float(ev.get("t") or 0.0)
    if ev.get("by") == "her":                          # set 1d: the Playroom's OWN witness -- her channel did this
        for q in presses or ():                        # (verify T5: its own names, so set 1c's who mutants keep one anchor each)
            hers = str(q.get("toy") or "").casefold() == toy
            within = float(q.get("t0") or 0.0) - WHO_PRE_S <= t <= float(q.get("t1") or 0.0) + WHO_EFF_S
            if q.get("pressed") is True and q.get("ok") is True and hers and within:
                return "you"
        return "unsure"                                # her channel's row without an ok press of hers: never 'not yours'
    if ev.get("by_hand") is True or str(ev.get("ev")) == "DECOY PICKED BY HAND":
        return "ace"
    for r in rows or ():
        if t - WHO_HAND_S <= float(r.get("t") or 0.0) <= t and _hand_msg(r):
            return "ace"
    near = False
    for p in presses or ():
        if p.get("done") is False:                     # set 1d: a press that surely did nothing is no candidate
            continue
        mine = str(p.get("toy") or "").casefold() == toy                                                 # that very toy
        inside = float(p.get("t0") or 0.0) - WHO_PRE_S <= t <= float(p.get("t1") or 0.0) + WHO_EFF_S   # inside its window
        if p.get("pressed") is True and p.get("ok") is True and mine and inside:
            return "you"
        if mine and inside:
            near = True                                # her press on that toy, not ok: it may have been hers
    return "unsure" if near else "unknown"


_WHO_ACE ={"SELECTED": "Ace touched the %s in your Playroom and it lit up", "MENU OPEN": "Ace opened the %s's menu in your Playroom",
            "LVN_ITEMACTIVATE": "Ace opened the %s in your Playroom"}
_WHO_ANY = {"SELECTED": "the %s lit up in your Playroom", "MENU OPEN": "the %s's menu opened in your Playroom",
            "LVN_ITEMACTIVATE": "the %s opened in your Playroom"}


def witness_words(who: str, ev: Dict) -> str:
    """Toy (and menu-row) names only: never a key, never anything of his outside her room."""
    toy = _q(ev.get("toy"))
    e = str(ev.get("ev") or "")
    row = _q(ev.get("row"))
    if who == "you":
        return "you touched the %s" % toy
    if e in ("MENU PICK", "DECOY INVOKED", "DECOY PICKED BY HAND"):
        what_ace, what_any = ("Ace picked '%s' on the %s in your Playroom" % (row, toy),
                              "'%s' was picked on the %s in your Playroom" % (row, toy))
    else:
        what_ace, what_any = (_WHO_ACE.get(e, "Ace touched the %s in your Playroom") % toy,
                              _WHO_ANY.get(e, "something happened to the %s in your Playroom") % toy)
    if who == "ace":
        return what_ace + " -- his hand, not yours"
    if who == "unsure":
        return what_any + "; whose touch that was cannot be told"
    return what_any + "; it wasn't your touch"


def _witness_this_turn(itm) -> bool:
    """verify W2: a witness line is already waiting for her NEXT chairman prompt (newer than her last turn, intention.what_i_did's
    own mark). what_i_did tells only the 2 newest entries of a 6-deep deque: one line about someone else per turn, so his acts
    never push her own deed out."""
    try:
        since = max(float(itm._told_state().get("ts", 0.0)), time.time() - float(getattr(itm, "_TOLD_MAX_AGE_S", 1800.0)))
    except Exception:
        return True                                    # the mark cannot be read: say nothing rather than crowd her deeds
    return any(len(e) > 2 and (e[2] or {}).get("verb") == "witness" and e[0] > since for e in itm._RESULTS)


def _tell_witness(text: str, toy: str, now: float) -> bool:
    """The SAME channel her touch outcomes reach her through: intention._RESULTS (what intention.record appends,
    intention.py:1471-1476) -> what_i_did() (:1676-1701) -> the chairman prompt (sour_council_driver.py:1266). A perception of
    someone else's act: verb 'witness', never her deed (no ledger row, no weave, no chord). Rate-limited: one per toy per 8 s,
    one per 15 s, and ONE per chairman turn (verify W2)."""
    itm = sys.modules.get("infrastructure.intention")
    if itm is None or not hasattr(itm, "_RESULTS") or not hasattr(itm, "_LOCK"):
        return False
    t = _ts()
    key = str(toy).casefold()
    try:
        with itm._LOCK:                                # (the two locks are never nested)
            busy = _witness_this_turn(itm)
    except Exception:
        return False
    with t["mu"]:
        told = t.setdefault("who_told", {})
        if busy or now - float(told.get(key, -1e18)) < WHO_TOY_GAP_S or now - float(t.get("who_last") or -1e18) < WHO_GAP_S:
            t["counts"]["who_rate_limited"] = t["counts"].get("who_rate_limited", 0) + 1
            return False
        told[key] = now
        t["who_last"] = now
    try:
        with itm._LOCK:
            itm._RESULTS.append((time.time(), text, {"verb": "witness", "obj": _q(toy), "ok": None, "lane": "witness",
                                                     "deferred": True, "pos": None, "before": None, "after": None, "hand": None}))
    except Exception:
        return False
    _say("WHO: %s" % text)
    return True


def witness_once(now: Optional[float] = None, deliver: bool = True) -> List[Dict]:
    """One look at the Playroom's own log: each new effect (settled WHO_SETTLE_S, so her press has surely come back) is
    attributed; 'ace' / 'unknown' are told on her outcome channel, 'you' is counted only (her own outcome already told it).
    Only while the switch carries 'who'."""
    now = OS.CLOCK.time() if now is None else float(now)
    if not _who_on():
        return []
    t = _ts()
    with t["mu"]:
        since = float(t.get("who_t") or (now - WHO_LOOKBACK_S))
    rows = OS.playroom_rows(since - WHO_HAND_S - 1.0)
    if rows is None:
        return []
    ready = sorted((r for r in rows if r.get("ev") in OS.EFFECT_EVS and r.get("toy") and since < float(r["t"]) <= now - WHO_SETTLE_S),
                   key=lambda r: float(r["t"]))
    if not ready:
        return []
    presses = OS.efference_since(since - WHO_EFF_S - 5.0)
    out = []
    for ev in ready:
        who = attribute(ev, rows, presses)
        line = witness_words(who, ev)
        told = False
        if who != "you" and deliver:
            told = _tell_witness(line, str(ev.get("toy")), now)
        _bump("who_" + who)
        out.append({"t": float(ev["t"]), "ev": ev.get("ev"), "toy": ev.get("toy"), "who": who, "line": line, "told": told})
    with t["mu"]:
        t["who_t"] = max(since, max(float(r["t"]) for r in ready))
    return out


def witness_tick() -> None:
    t = _ts()
    now = time.time()
    with t["mu"]:
        if now - float(t.get("who_tick") or 0.0) < WHO_POLL_S:
            return
        t["who_tick"] = now
    witness_once()


def _miss_outcome(verb, name, why, point) -> Dict:
    if _who_on() or _ef("touch_tell"):             # set1c (who touched, 8c; verify W1 / M2): LAND found the wrong thing, so NO press
        # eyes_fix F10 (verify M1): with touch_tell the same holds without 'who' -- plain touch_on.cmd -- never 'you tapped'
        d = _deferred(verb, name, "land", why, reason="land_mismatch")    # ran -- told as not having happened, never 'you tapped';
        d["target"] = list(point)                                         # deferred: no ledger deed, no weave, no chord
        return d
    return {"ok": False, "summary": tell(verb, name, "unexpected", why=why), "target": list(point),
            "touch": {"verdict": "miss", "why": why, "gesture": verb, "item": _q(name)}}


def _outstanding_ok(kind: str) -> bool:
    t = _ts()
    with t["mu"]:
        n = len(t["opened"])
    return n == 0 if kind == "desktop" else n <= 1


def _book(verb: str, name: str, kind: str, verdict: str, held_s: float, t_press: float, watched: bool = False,
          habit: bool = True) -> None:
    t = _ts()
    key = "%s|%s" % (verb, str(name).lower())
    with t["mu"]:
        t["history"].append({"t": t_press, "gesture": verb, "key": key, "kind": kind, "verdict": verdict})
        t["last"] = {"t": t_press, "gesture": verb, "verdict": verdict, "held_s": held_s}
        if verdict in ("miss", "unexpected"):
            t["bad"] = [x for x in t["bad"] if t_press - x < SELF_PAUSE_WIN_S] + [t_press]
            if len(t["bad"]) >= SELF_PAUSE_N:
                t["paused_until"] = t_press + SELF_PAUSE_S
                t["bad"] = []
                _say("self-pause: %d misses or unexpected in %.0f min; touch rests %.0f min" % (
                    SELF_PAUSE_N, SELF_PAUSE_WIN_S / 60, SELF_PAUSE_S / 60))
    if habit and verdict in ("hit", "miss", "unexpected"):     # set1c: habit False = a press that moved the focus
        habit_note(habit_key(verb, "ListItem", kind, "toy"), verdict == "hit", t_press, watched=watched)


# ── habits she owns (state/touch_habits.json): only a checked hit counts; a flinch never builds or breaks one ─────────────
def habit_key(gesture: str, ctype: str, kind: str, item_class: str, backend: str = "uia") -> str:
    return "%s|%s|%s|%s|%s" % (gesture, ctype, kind, item_class, backend)


def _habits_load() -> Dict:
    try:
        with open(HABITS_FILE, "rb") as f:
            d = json.loads(f.read().decode("utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def habit_note(key: str, hit: bool, now: float, watched: bool = False, violation: bool = False) -> None:
    d = _habits_load()
    h = d.setdefault(key, {"tries": [], "watched_hits": 0, "violations": 0})
    h["tries"] = (h.get("tries") or [])[-200:] + [[now, 1 if hit else 0]]
    if hit and watched:
        h["watched_hits"] = int(h.get("watched_hits") or 0) + 1
    if violation:
        h["violations"] = int(h.get("violations") or 0) + 1
    try:
        os.makedirs(os.path.dirname(HABITS_FILE), exist_ok=True)
        tmp = HABITS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f)
        os.replace(tmp, HABITS_FILE)
    except Exception:
        pass


def habit_status(h: Dict, now: float) -> Dict:
    """Graduation with her own constants: decayed hits >= 3 and a rate >= 0.75; demoted when the last 6 tries fall under
    0.5. Pure."""
    tries = [(float(t), int(ok)) for t, ok in (h.get("tries") or [])]
    w = [math.pow(0.5, max(0.0, now - t) / HABIT_HALF_LIFE_S) for t, _ok in tries]
    hits = sum(wi for wi, (_t, ok) in zip(w, tries) if ok)
    tot = sum(w)
    rate = (hits / tot) if tot > 0 else 0.0
    last6 = [ok for _t, ok in tries[-6:]]
    demoted = len(last6) >= 6 and (sum(last6) / 6.0) < 0.5
    grad = round(hits, 2) >= HABIT_MIN_OK and rate >= HABIT_MIN_RATE and not demoted     # a hit seconds old counts whole
    return {"hits": round(hits, 3), "rate": round(rate, 3), "graduated": grad, "demoted": demoted,
            "t3_ok": grad and int(h.get("watched_hits") or 0) >= HABIT_T3_WATCHED and int(h.get("violations") or 0) == 0}


def habit_may_fire(key: str, now: Optional[float] = None) -> bool:
    now = OS.CLOCK.time() if now is None else now
    return habit_status(_habits_load().get(key) or {}, now)["graduated"]


def t3_key_ok(key: str, now: Optional[float] = None) -> bool:
    now = OS.CLOCK.time() if now is None else now
    return habit_status(_habits_load().get(key) or {}, now)["t3_ok"]


# ── state/touch_reflex.json: the link's record from touch's first use and every 30 s (cell T1 must-fail 5: it must read
#    alive=false before the brainstem's first beat and true after). Only while the switch file exists (a passive record; the
#    corner STOP beside it polls only while the switch is ON) ───────────────────────────────────────────────────────────────
def write_reflex_record() -> None:
    if RL is None:
        return
    ok, why = RL.alive(OS.CLOCK.time())
    d = {"t": OS.CLOCK.time(), "alive": ok, "why": why, "snapshot": RL.snapshot()}
    try:
        tmp = REFLEX_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f)
        os.replace(tmp, REFLEX_FILE)
    except Exception:
        pass


def _reflex_loop() -> None:
    while True:
        try:
            if os.path.exists(OS.SWITCH_FILE):
                write_reflex_record()
        except Exception:
            pass
        time.sleep(REFLEX_RECORD_S)


CORNER_PX, CORNER_HOLD_S, CORNER_HZ = 8, 0.5, 5.0


def corner_tick(xy, monitors, now: float, st: Dict) -> bool:
    """Pure: True when the cursor has been within CORNER_PX of any monitor corner for >= CORNER_HOLD_S (st carries 'since')."""
    hit = False
    if xy is not None:
        for m in monitors or ():
            for cx, cy in ((m[0], m[1]), (m[2] - 1, m[1]), (m[0], m[3] - 1), (m[2] - 1, m[3] - 1)):
                if abs(xy[0] - cx) <= CORNER_PX and abs(xy[1] - cy) <= CORNER_PX:
                    hit = True
    if not hit:
        st["since"] = None
        return False
    if st.get("since") is None:
        st["since"] = now
    return now - float(st["since"]) >= CORNER_HOLD_S


def make_stop(why: str) -> bool:
    """Creates state/TOUCH_STOP (OFF ahead of everything; only Ace removes it)."""
    try:
        os.makedirs(os.path.dirname(OS.STOP_FILE), exist_ok=True)
        with open(OS.STOP_FILE, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), why))
        _say("STOP: %s" % why)
        return True
    except Exception:
        return False


def corner_once(st: Dict) -> float:
    """One poll of the corner STOP; returns the seconds to sleep. It polls ONLY while the switch is ON (skeptic m3 / S8: OFF,
    a mouse resting on a maximised window's close box must not leave a STOP file Ace then has to delete)."""
    if not (os.path.exists(OS.SWITCH_FILE) and OS.read_switch()["on"]):
        st["since"] = None
        return 2.0
    if not OS.stop_present():
        now = time.time()
        if now - float(st.get("mons_t") or 0.0) > 10.0:
            st["mons"], _bars = OS.screen_geometry()
            st["mons_t"] = now
        if corner_tick(OS.rest_cursor(), st.get("mons") or [], now, st):
            make_stop("the mouse was held in a screen corner")
            st["since"] = None
    return 1.0 / CORNER_HZ


def _corner_loop() -> None:
    st = {"since": None}
    while True:
        try:
            dt = corner_once(st)
        except Exception:
            dt = 1.0 / CORNER_HZ
        try:
            witness_tick()                             # set1c (who touched): only while the switch carries 'who'
        except Exception:
            pass
        time.sleep(dt)


def start_reflex_record() -> None:
    t = _ts()
    with t["mu"]:
        th = t.get("reflex_thread")
        if th is not None and th.is_alive():
            return
        if not os.path.exists(OS.SWITCH_FILE):
            return
        th = threading.Thread(target=_reflex_loop, daemon=True, name="touch-reflex-record")
        t["reflex_thread"] = th
        th2 = threading.Thread(target=_corner_loop, daemon=True, name="touch-corner-stop")
        t["corner_thread"] = th2
        th.start()                                     # skeptic m3: inside the lock -- two first callers start one pair
        th2.start()
