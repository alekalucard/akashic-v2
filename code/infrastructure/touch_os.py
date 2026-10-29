"""touch_os -- the ONE function in her that can press: press(request). 2026-10-05 (Nous, nous_builds/touch_screen set 1;
DESIGN.md 2d, 2e, 2f, 4a, 7, 8, 11).

Ace, 2026-10-01: "for now she would need a safety feature to work out the bugs and teach her so she is not opening anything
or everything, deleting stuff etc". Ace, 2026-10-05: the no-no list is her own withdrawal reflex, and nothing overrides it.

What lives here and nowhere else:
  * the only calls of a UIA write (Select, RemoveFromSelection, Invoke, Expand, ShowContextMenu, WindowPattern.Close), made
    on ONE long-lived 'touch-worker' thread that owns every UIA object (MTA, CUIAutomation8, 3000 ms transaction timeout);
  * the guard, re-run ON THAT WORKER immediately before the call (DESIGN 2d steps 1-11): STOP file, the switch (fails closed,
    expires <= 2 h), the latches (violation / stuck / unfelt / ... -- in memory first), her brainstem beating
    (reflex_link.alive, read only in the closed direction), the touch_lists sha pin, Ace first (both input channels, hook
    alive, not waiting, idle floor, foreground rule, NOTHING moved since the 1.5 s announce began = his veto), the no-no
    check (authoritative; deny before allow), NOT-YET (allow-list, control types, CLEARED_CALLS), the item's identity, a
    rate backstop, the door's per-deed nonce. If more than 100 ms pass between step 1 and the call, steps 1, 2 and 4-7 run
    again once; if 100 ms pass again it defers. The last line before the call re-reads STOP, the switch's mtime and the
    physical-input stamp;
  * the sentinels across the call (cursor >= 200 Hz, GetLastInputInfo, the hook's injected count): one unexplained input
    latches the layer OFF; a call that has not returned in 4 s latches 'stuck'.
No keys and no drag exist in this module. No touch tool is registered anywhere and no postal topic is subscribed; this
module never publishes and never reads a fairy. It reaches user32 and the UIA client ONLY through _u32() and _uia(), so the
cell T0 harness can replace them. In set 1 touch_lists.CLEARED_CALLS is EMPTY: every write is refused (NOT-YET) in her
process until probe F1 clears a call 20/20 and touch_lists is rebuilt.
Skeptic fixes (10-05, BUILD.md "Skeptic findings and fixes"): B1 integrity() typed its SID helpers (an untyped 64-bit pointer
crashed the whole process); m1 the touch-worker initialises COM as MTA even when it is comtypes' first importer; M1
importlib.reload of this module, touch_lists or reflex_link latches 'reload' (a body re-run marks the module); m8 the shared
state is created under a lock; S6 a changed brainstem id latches 'beaters'; S9 the guard checks the stage's roots before any
UIA read; m2 Ace's two input channels are compared with the announce once more immediately before the call.
Set 1c (10-09, nous_builds/touch_screen/set1c; Ace: "is it possible to let her do stuff while im doing stuff?"): PARALLEL PLAY,
Playroom only -- a press marked 'parallel' is vetoed by Ace IN HER ROOM (the Playroom in front, his cursor over it or over a
window of its process, a reply to him pending, input in the Playroom's own log), never by his hands elsewhere; the FOCUS LATCH
(the foreground window, its GUI thread and that thread's keyboard focus, read before anything of hers shows and again before
and after the call; any change -> parallel play OFF for the touch session, in MEMORY, the strict rule back); her own presses
kept as her EFFERENCE COPY (efference_since) so 'you touched' can only come from a press that ran and came back ok; and the
VERIFIED Playroom's toy names for her eyes (eyes_playroom). Every set1c switch key is optional and OFF when absent.
Fold (10-09, Ace decision 1): her toy-name eyes have their OWN switch, state/eyes_fix.json 'toy_names' (eyes_fix_switch),
independent of touch arming, touch_off, switch_off and every touch latch; the touch switch no longer carries 'eyes'. Its 'log'
key logs the front window whenever the full-screen rule can fire (_fullscreen_note; DIAGNOSIS C10, F1 vs F2).
Set 1d (10-12, nous_builds/touch_screen/set1d; probe F9 10-12 run/probe_F9_20261012_100439.json: a UIA Select / ShowContextMenu
on a BACKGROUND Playroom moved Ace's foreground and keyboard focus into it and his typing landed there): HER OWN CHANNEL. With the
switch's 'channel' key (set1d/touch_on.cmd --channel; --parallel forces it), a tap or hold on a VERIFIED set 1d Playroom's toy goes
over the Playroom's own local named pipe (set1d/playroom/playroom_channel.py, protocol 1; _RealChannel, _chan()) and the Playroom
does it INSIDE its own window, activating nothing -- instead of Windows' accessibility write path. Parallel play then REQUIRES the
channel (no UIA fallback); without it the strict rule may use UIA only with the Playroom IN FRONT (probe F1's condition). The guard,
every read, the sentinels and the efference copy are unchanged. 'channel' absent = set 1c exactly (route_for returns 'uia').
Set 1e (10-13, nous_builds/touch_screen/set1e; probe F9c 10-13 run/probe_F9_20261013_153814.json: her channel touches left Ace's
focus alone 20/20, her strip and marker WINDOWS took it): HER FINGER CUE inside her own Playroom. With the switch's 'cue' key
(set1e/touch_on.cmd --cue / --parallel; it needs 'channel'), a tap / hold on the VERIFIED set 1e Playroom (its script, its channel
file saying "cue": true) is announced by 'cue <toy> <ms>' over its channel (cue_route, cue_show, cue_cancel): the Playroom draws it
INSIDE its own window and touch.py spawns no marker and no strip for that deed. Such a press is CUED and goes ONLY over the channel
(route_for). PARALLEL play needs 'cue' in the switch (_set1c_bad, P1) and a cued press (route_for, P1). 'cue' absent = set 1d
exactly, except P1 (a 'parallel' switch without 'cue' reads OFF: set 1d's strip / marker took his focus in parallel play).
Perma (10-21, nous_builds/touch_perma_1021; Ace: "we might want to make the touch system more a perma thing. gives us a step into
running the system with her thoughts or internally precieved body motion."): the switch's 'perma' key (touch_perma_1021/touch_on.cmd
--perma, a typed yes) is a PERMANENT arm: no 'until', no expiry; the Playroom only (stage T1), watched; every fence of set 1e stays.
Its latch rule (Ace's pick): a STUCK call TRIPS touch -- off at once, felt as one flinch (phase 'trip'), logged and counted
(state/touch_trips.jsonl); after a cool-down (the switch's 'cooldown_s', default 10 min) it clears ITSELF only if the stuck call has
come back, the flinch was felt and nothing else is latched; three trips in an hour = a hard latch only Ace clears. Every other latch
kind, and every latch under a timed switch, is exactly today's. 'perma' absent / false = set 1e exactly.
Revert: delete infrastructure/touch.py (intention's optional import then runs today's path from her next start).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import queue
import secrets
import sys
import threading
import time
from typing import Dict, List, Optional, Tuple

from infrastructure import touch_lists as TL
try:
    from infrastructure import reflex_link as RL
except Exception:                                    # no link = touch is OFF at arm (DESIGN 7f); never an allow
    RL = None

try:                                                 # skeptic M1: a second run of this body = importlib.reload in place
    _RELOADED = bool(_BODY_RAN)                      # noqa: F821
except NameError:
    _RELOADED = False
_BODY_RAN = True

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
STATE_DIR = os.path.join(_ROOT, "state")
SWITCH_FILE = os.path.join(STATE_DIR, "touch_screen.json")
STOP_FILE = os.path.join(STATE_DIR, "TOUCH_STOP")
LATCH_FILE = os.path.join(STATE_DIR, "touch_latch.json")
BUILD_DIR = "F:/Sandbox/Akashic_phasing/nous_builds/touch_screen"
PLAYROOM_RUN = BUILD_DIR + "/run/playroom.json"
PLAYROOM_EVENTS = BUILD_DIR + "/run/playroom_events.jsonl"
PLAYROOM_SCRIPT_TAIL = "touch_screen/set1/playroom/playroom.py"
PLAYROOM_SCRIPT_TAIL_1D = "touch_screen/set1d/playroom/playroom.py"    # set 1d: the Playroom with her own channel
PLAYROOM_SCRIPT_TAIL_1E = "touch_screen/set1e/playroom/playroom.py"    # set 1e: + her finger cue drawn inside it
PLAYROOM_CHANNEL = BUILD_DIR + "/run/playroom_channel.json"             # set 1d: its pipe's name + the per-run token
PLAYROOM_TITLE = "Sour's Playroom"
PLAYROOM_WND = "SourPlayroomWnd"
PLAYROOM_MENU = "SourPlayroomMenu"
PLAYROOM_TOY = "SourPlayroomToy"
PLAYROOM_CLASSES = frozenset({PLAYROOM_WND, PLAYROOM_MENU, PLAYROOM_TOY})
DESKTOP_CLASSES = frozenset({"Progman", "WorkerW"})
STAGE_ROOT_CLASSES = {"T1": PLAYROOM_CLASSES, "T2": PLAYROOM_CLASSES | DESKTOP_CLASSES, "T3": PLAYROOM_CLASSES | DESKTOP_CLASSES}
STAGES = ("T1", "T2", "T3")
SWITCH_KEYS = frozenset({"on", "stage", "watched", "allow", "allow_sha256", "deny_sha256", "gestures", "until", "by",
                         "parallel", "who", "park_s",                 # set1c: optional; a malformed one = OFF (_set1c_bad)
                         "channel",                                   # set 1d: optional true / false; absent = set 1c exactly
                         "cue",                                       # set 1e: optional true / false; absent = set 1d exactly
                         "perma", "cooldown_s"})                      # perma (10-21): optional; absent / false = the timed switch
# fold 10-09 (Ace decision 1): 'eyes' left the touch switch -- her toy-name eyes are state/eyes_fix.json's 'toy_names'
# (eyes_fix_switch); an 'eyes' key here is now an unknown key, so the touch switch fails CLOSED, as every unknown key does.
ALLOW_KEYS = frozenset({"stage", "roots", "items", "menu_rows", "expand_only"})
SET1_LANES = frozenset({"ask"})                      # habit / chain lanes are NOT-YET until a later set (T3, T16)
UNTIL_MAX_S = 7200.0
DEADLINE_S = 0.100
WATCHDOG_S = 4.0
UIA_TRANSACTION_MS = 3000
RECT_TOL_PX = 4
IDLE_FLOOR_S = {"playroom": 5.0, "desktop_watched": 5.0, "desktop_tap": 30.0, "desktop_open": 60.0}
HOOK_DEAD_MS = 2000
MIN_PRESS_GAP_S = 2.0                                # a backstop under touch.py's own cooldowns
DAY_PRESS_CAP = 100
SENTINEL_HZ = 200.0
SENTINEL_PRE_S = 0.05
SENTINEL_POST_S = 0.5
PAUSE_EXES = frozenset({"valheim.exe", "lockapp.exe"})
# set1c (10-09): parallel play, the focus latch, her efference copy, her eyes' toy names
PARALLEL_GESTURES = frozenset({"tap", "hold"})      # double_tap never plays in parallel
PARK_MAX_S = 12.0                                    # the park knob's ceiling (Ace: "up to N s, default 12")
ROOM_INPUT_EVS = frozenset({"WM_LBUTTONDOWN", "WM_LBUTTONUP", "WM_LBUTTONDBLCLK", "WM_RBUTTONDOWN", "WM_RBUTTONUP",
                            "WM_MBUTTONDOWN", "WM_KEYDOWN", "WM_KEYUP", "WM_SYSKEYDOWN", "WM_SYSKEYUP", "WM_CHAR", "WM_MOUSEMOVE"})
HAND_EVS = ROOM_INPUT_EVS - {"WM_MOUSEMOVE"}         # a button or a key: a hand (a move can be synthesised under a still cursor)
EFFECT_EVS = frozenset({"SELECTED", "MENU OPEN", "MENU PICK", "DECOY INVOKED", "DECOY PICKED BY HAND", "LVN_ITEMACTIVATE"})
ROOM_LOG_KEEP_S = 120.0
ROOM_LOG_TAIL_BYTES = 65536
EFFERENCE_KEEP = 64
MENU_GAP_PX, MENU_W_PX, MENU_ROW_PX, MENU_PAD_PX = 6, 210, 28, 8   # = set1/playroom/playroom.py _open_menu (verify S1)
# set 1d (10-12): her own channel to her own Playroom (set1d/playroom/playroom_channel.py protocol 1)
CHANNEL_GESTURES = frozenset({"tap", "hold"})
CHANNEL_PROTO = 1
CHANNEL_TIMEOUT_S = 2.5                              # the whole call (connect, hello, answer): inside WATCHDOG_S with the sentinel
CHANNEL_MAX_MSG = 4096
CHANNEL_PIPE_HEAD = "\\\\.\\pipe\\SourPlayroom-"
PANEL_MARGIN_PX = 2                                  # = playroom_model.PANEL_MARGIN_PX: the set 1d panel stays inside the client area
# set 1d (10-13, Boot L): 'place' -- her Playroom moves / resizes itself (playroom_model.place_rect decides where)
PLACE_SPOTS = ("left", "right", "centre", "top", "bottom", "top-left", "top-right", "bottom-left", "bottom-right", "bigger",
               "smaller")                            # = playroom_model.PLACE_SPOTS = playroom_channel.PLACE_SPOTS (test C11)
PLACE_Z_WORDS = frozenset({"front", "forward", "back", "behind", "topmost", "top-most", "above", "on-top"})
PLACE_GAP_S = 10.0                                   # her side's own rate (the Playroom keeps its own, playroom_model.PlaceLimiter)
PLACE_HOUR_CAP = 12
PLACE_TOL_PX = 4
# set 1e (10-13): her FINGER CUE drawn inside her own Playroom ('cue <toy> <ms>', set1e/playroom), instead of her strip and marker
CUE_MS_MIN, CUE_MS_MAX = 200, 4000                   # = set1e playroom_model / playroom_channel (test K01)
CUE_CANCEL_TIMEOUT_S = 1.0                           # taking a cue away is best effort: a short wait
# perma (10-21, nous_builds/touch_perma_1021): a PERMANENT arm and the latch rule that goes with it
TRIPS_FILE = os.path.join(STATE_DIR, "touch_trips.jsonl")   # every trip and every clear, one line each (append only)
PERMA_COOLDOWN_S = 600.0                             # a stuck trip rests this long (Ace: "e.g. 10 minutes"); 'cooldown_s' may change it
PERMA_COOLDOWN_MIN_S, PERMA_COOLDOWN_MAX_S = 120.0, 3600.0   # ... clamped to this range
PERMA_HARD_TRIPS, PERMA_HARD_WINDOW_S = 3, 3600.0    # three trips in an hour: a HARD latch, only Ace clears it
PERMA_REOFFER_S, PERMA_REOFFER_MAX = 60.0, 10        # a trip her brainstem never took is offered again once the rest is over (<= this often)
_BOOT = secrets.token_hex(8)                         # this process: a trip file of ANOTHER boot belongs to a stuck call that died with it
_CLEAR_LOCK = threading.Lock()                       # one self-clear at a time; a reader that cannot take it sees the latch (safe side)
LATCH_KINDS = ("violation", "stuck", "unfelt", "reload", "beaters", "hook_dead", "sha", "latch_write", "dpi")
_MODS = ("infrastructure.touch", "infrastructure.touch_os", "infrastructure.touch_lists", "infrastructure.reflex_link")

UIA_CTYPES = {50000: "Button", 50001: "Calendar", 50002: "CheckBox", 50003: "ComboBox", 50004: "Edit", 50005: "Hyperlink",
              50006: "Image", 50007: "ListItem", 50008: "List", 50009: "Menu", 50010: "MenuBar", 50011: "MenuItem",
              50012: "ProgressBar", 50013: "RadioButton", 50014: "ScrollBar", 50015: "Slider", 50016: "Spinner",
              50017: "StatusBar", 50018: "Tab", 50019: "TabItem", 50020: "Text", 50021: "ToolBar", 50022: "ToolTip",
              50023: "Tree", 50024: "TreeItem", 50025: "Custom", 50026: "Group", 50027: "Thumb", 50028: "DataGrid",
              50029: "DataItem", 50030: "Document", 50031: "SplitButton", 50032: "Window", 50033: "Pane", 50034: "Header",
              50035: "HeaderItem", 50036: "Table", 50037: "TitleBar", 50038: "Separator", 50039: "SemanticZoom", 50040: "AppBar"}
SELECTABLE_CTYPES = frozenset({"ListItem", "DataItem", "TreeItem"})


# ── clock (the cell T0 harness replaces CLOCK with a fake one) ──────────────────────────────────────────────────────────────
class _Clock:
    def time(self) -> float:
        return time.time()

    def perf(self) -> float:
        return time.perf_counter()

    def sleep(self, s: float) -> None:
        time.sleep(max(0.0, float(s)))


CLOCK = _Clock()


def _after_guard() -> None:
    """A seam between the guard and the call. In her process it does nothing; cell T0 plants stalls here."""
    return None


def _say(msg: str) -> None:
    try:
        print(("[TouchOS] %s" % msg).encode("ascii", "replace").decode("ascii"), flush=True)   # ASCII only: never the failure
    except Exception:
        pass


# ── process-wide state on _sour_council_shared (survives a hot reload; a reload itself latches OFF) ──────────────────────
_LOCAL = {}
_SH_INIT = threading.Lock()                          # skeptic m8: two first callers must not each build (and race) the state


def _sh() -> Dict:
    m = sys.modules.get("_sour_council_shared")
    st = _LOCAL if m is None else getattr(m, "TOUCH", None)
    if st is not None and "mu" in st:
        return st
    with _SH_INIT:
        if m is not None:
            st = getattr(m, "TOUCH", None)
            if st is None:
                st = {}
                m.TOUCH = st
        else:
            st = _LOCAL
        if "mu" not in st:
            st.update({"mu": threading.RLock(), "latch": {}, "latch_write_failed": False, "mod_ids": {}, "presses": [],
                       "worker": None, "late": 0, "imports": {}, "sense_errors": [], "stats": {}})
    return st


def _bump(key: str, n: int = 1) -> None:
    st = _sh()
    with st["mu"]:
        st["stats"][key] = st["stats"].get(key, 0) + n


# ── latches: in memory FIRST, then the file (8-retry replace); a failed write keeps the layer OFF for the boot ───────────
def latch(kind: str, why: str) -> None:
    st = _sh()
    with st["mu"]:
        new = str(kind) not in st["latch"]
        st["latch"].setdefault(str(kind), str(why)[:200])
        snap = dict(st["latch"])
    if new and str(kind) == "stuck":
        _perma_trip(str(why))                            # perma (10-21): under a permanent switch a NEW stuck latch is a counted, felt trip
    ok = _write_latch_file(snap)
    if not ok:
        with st["mu"]:
            st["latch_write_failed"] = True
    _say("LATCH %s: %s (file %s)" % (kind, why, "written" if ok else "WRITE FAILED: OFF for this boot"))


def _write_latch_file(snap: Dict) -> bool:
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        tmp = LATCH_FILE + ".tmp"
        doc = {"latched": snap, "t": CLOCK.time(), "note": "touch is OFF; only Ace clears this (delete the file; "
               "the in-memory latch ends with her next boot)"}
        blk = _sh().get("trip_block")                    # perma (10-21): a stuck trip of a permanent arm says how it may clear
        if blk and "stuck" in snap:
            doc["selfclear"] = dict(blk)
            doc["note"] = ("touch is OFF (permanent arm, a stuck call): it rests, then clears itself once the stuck call has come "
                           "back and the cool-down is over; three trips in an hour = a HARD latch, only Ace clears it"
                           if blk.get("eligible") is True else
                           "touch is OFF: a HARD latch (three trips in an hour, or a trip that could not be logged); only Ace "
                           "clears this (move the file aside, restart her)")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(doc, f)
        for _ in range(8):
            try:
                os.replace(tmp, LATCH_FILE)
                return True
            except PermissionError:
                CLOCK.sleep(0.05)
        return False
    except Exception:
        return False


def latch_state() -> Tuple[bool, Dict]:
    """(latched, reasons). Memory first; a failed latch write; then the file on disk (unreadable = latched).
    perma (10-21): first, a stuck trip of a PERMANENT arm whose cool-down is over may clear itself (_perma_clear_if_due)."""
    _perma_clear_if_due()
    st = _sh()
    with st["mu"]:
        mem = dict(st["latch"])
        wf = bool(st["latch_write_failed"])
    if mem or wf:
        if wf:
            mem.setdefault("latch_write", "a latch could not be written to disk: OFF for this boot")
        return True, mem
    if os.path.exists(LATCH_FILE):
        try:
            with open(LATCH_FILE, "rb") as f:
                d = json.loads(f.read().decode("utf-8-sig"))
            return True, dict((d or {}).get("latched") or {"file": "latch file present"})
        except Exception:
            return True, {"file": "latch file present and unreadable"}
    return False, {}


# ── perma (10-21): the stuck trip of a PERMANENT arm -- off at once and FELT; it rests, then clears itself; three in an hour = a
#    hard latch only Ace clears. Every other latch kind, and every latch under a timed switch, is exactly today's ───────────────
def _perma_sw(now: float) -> Optional[Dict]:
    """The switch's data when the switch is VALID and permanent (perma true), else None. Read-only; never raises."""
    try:
        sw = read_switch(now)
        d = sw.get("data") or {}
        return d if sw.get("on") and d.get("perma") is True else None
    except Exception:
        return None


def _perma_cooldown(d: Optional[Dict]) -> float:
    """How long a trip rests: the switch's 'cooldown_s', clamped to PERMA_COOLDOWN_MIN_S..PERMA_COOLDOWN_MAX_S (default 10 min)."""
    try:
        c = float((d or {}).get("cooldown_s", PERMA_COOLDOWN_S))
    except Exception:
        return PERMA_COOLDOWN_S
    if c != c:
        return PERMA_COOLDOWN_S
    return min(PERMA_COOLDOWN_MAX_S, max(PERMA_COOLDOWN_MIN_S, c))


def _trip_rows() -> Tuple[Optional[List[Dict]], str]:
    """The trip log's recent rows (its last 64 KB). -> (rows, '') | ([], '') when there is no log yet | (None, why) when it exists
    and cannot be read (then nothing can be counted honestly)."""
    try:
        with open(TRIPS_FILE, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 65536))
            data = f.read()
    except FileNotFoundError:
        return [], ""
    except Exception as e:
        return None, type(e).__name__
    rows = []
    for line in data.splitlines():
        try:
            r = json.loads(line.decode("utf-8"))
        except Exception:
            continue
        if isinstance(r, dict) and isinstance(r.get("t"), (int, float)) and not isinstance(r.get("t"), bool):
            rows.append(r)
    return rows, ""


def _trip_append(row: Dict) -> bool:
    """One line to the trip log (append only, flushed to disk). False = it could not be written."""
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        line = (json.dumps(row, sort_keys=True) + "\n").encode("ascii")
        with open(TRIPS_FILE, "ab") as f:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())
        return True
    except Exception:
        return False


def _trip_flinch(now: float):
    """The trip FELT: one flinch (class 'unknown', phase 'trip') offered to her brainstem through reflex_link. -> its id, or None
    (not offered: the link is missing or full)."""
    try:
        if RL is None:
            return None
        fl = TL.make_flinch("unknown", "a touch call did not return", "trip")
        return RL.offer(TL.flinch_dict(fl, reach_frac=1.0, stop_px=0, t=now))
    except Exception:
        return None


def _perma_trip(why: str) -> None:
    """A NEW stuck latch. Under a permanent switch: count it (state/touch_trips.jsonl), make it felt, and record how it may clear
    (the 'trip_block' the latch file carries). Three in an hour, a log that cannot be read or written: HARD (only Ace clears).
    Under a timed switch or none: nothing here, the latch is today's. Never raises."""
    try:
        st = _sh()
        now = CLOCK.time()
        d = _perma_sw(now)
        if d is None:
            return
        cool, n, fid = _perma_cooldown(d), None, None
        hard, logged = True, False
        try:
            rows, _e = _trip_rows()
            if rows is not None:
                last_hard = max([float(r["t"]) for r in rows if r.get("ev") == "trip" and r.get("hard") is True] or [0.0])
                n = 1 + sum(1 for r in rows if r.get("ev") == "trip" and float(r["t"]) > last_hard
                            and 0.0 <= now - float(r["t"]) < PERMA_HARD_WINDOW_S)
                hard = n >= PERMA_HARD_TRIPS
            fid = _trip_flinch(now)
            logged = _trip_append({"t": now, "ev": "trip", "kind": "stuck", "why": str(why)[:120], "n_hour": n, "hard": hard,
                                   "cooldown_s": cool, "boot": _BOOT, "pid": os.getpid(), "flinch_id": fid,
                                   "offered": fid is not None})
        except Exception:
            pass
        hard = hard or not logged                    # a trip that cannot be counted honestly is a hard one
        with st["mu"]:
            st["trip"] = {"t": now, "fid": fid, "hard": hard, "cooldown_s": cool, "n_hour": n, "cleared": False}
            st["trip_block"] = {"eligible": not hard, "hard": hard, "trip_t": now, "cooldown_s": cool, "n_hour": n, "boot": _BOOT}
            st["stats"]["perma_trip"] = st["stats"].get("perma_trip", 0) + 1
            if hard:
                st["stats"]["perma_hard"] = st["stats"].get("perma_hard", 0) + 1
        _say("PERMA TRIP %s this hour: touch is OFF%s" % (n if n is not None else "?", " -- HARD latch, only Ace clears it" if hard
                                                         else ", it rests %.0f s and clears itself" % cool))
    except Exception:
        try:
            st = _sh()
            with st["mu"]:
                st["trip"] = {"t": CLOCK.time(), "fid": None, "hard": True, "cooldown_s": PERMA_COOLDOWN_S, "n_hour": None, "cleared": False}
                st["trip_block"] = {"eligible": False, "hard": True, "trip_t": CLOCK.time(), "boot": _BOOT}
        except Exception:
            pass


def _perma_due(now: float) -> Tuple[bool, Dict]:
    """May the latch end now? True only for a stuck trip of a PERMANENT arm: the switch is still valid and permanent, no STOP file,
    the latch (memory and file) holds nothing but 'stuck', no failed latch write, the trip is not hard, its cool-down is over, and --
    for this boot's trip -- the worker has nothing pending (the stuck call came back) and her brainstem FELT the trip's flinch; a
    trip of an EARLIER boot (the file's own block) clears by the same cool-down: its stuck call died with that process.
    -> (True, info) | (False, {'why': ...}). Read-only."""
    d = _perma_sw(now)
    if d is None:
        return False, {"why": "not a permanent arm"}
    if stop_present():
        return False, {"why": "the STOP file is there"}
    st = _sh()
    with st["mu"]:
        mem = dict(st["latch"])
        wf = bool(st["latch_write_failed"])
        tr = dict(st["trip"]) if st.get("trip") and not st["trip"].get("cleared") else None
        w = st.get("worker")
    fdoc, fkinds = None, set()
    if os.path.exists(LATCH_FILE):
        try:
            with open(LATCH_FILE, "rb") as f:
                fdoc = json.loads(f.read().decode("utf-8-sig"))
        except Exception:
            return False, {"why": "the latch file is unreadable"}
        fl = fdoc.get("latched") if isinstance(fdoc, dict) else None
        fkinds = set(fl) if isinstance(fl, dict) and fl else {"file"}
    if wf:
        return False, {"why": "a latch write failed"}
    if (set(mem) | fkinds) != {"stuck"}:
        return False, {"why": "something else is latched, or nothing is"}
    blk = fdoc.get("selfclear") if isinstance(fdoc, dict) else None
    if tr is not None:                               # this boot's trip
        if tr.get("hard") or "stuck" not in mem:
            return False, {"why": "a hard trip"}
        if fdoc is not None and not (isinstance(blk, dict) and blk.get("eligible") is True and blk.get("boot") == _BOOT):
            return False, {"why": "the latch file does not carry this boot's eligible trip"}
        t_trip, cool, n = tr.get("t"), tr.get("cooldown_s"), tr.get("n_hour")
    else:                                            # the file alone: a trip of an EARLIER boot
        if "stuck" in mem or fdoc is None or not isinstance(blk, dict):
            return False, {"why": "not a permanent arm's trip"}
        if blk.get("eligible") is not True or blk.get("hard") is True or blk.get("boot") == _BOOT:
            return False, {"why": "a hard trip, or this boot's own"}
        t_trip, cool, n = blk.get("trip_t"), blk.get("cooldown_s"), blk.get("n_hour")
    try:
        t_trip, cool = float(t_trip), min(PERMA_COOLDOWN_MAX_S, max(PERMA_COOLDOWN_MIN_S, float(cool)))
    except Exception:
        return False, {"why": "the trip's time is unreadable"}
    if now < t_trip or now - t_trip < cool:
        return False, {"why": "resting", "left_s": t_trip + cool - now}
    felt = None
    if tr is not None:                               # only this boot's trip has a stuck call that can still be out, and a flinch
        if w is None or not w.t.is_alive() or w.pending != 0:
            return False, {"why": "the stuck call has not come back"}
        felt = tr.get("fid") is not None and RL is not None and RL.felt_through(tr["fid"]) is True
        if not felt:
            return False, {"why": "the trip has not been felt", "reoffer": True}
    return True, {"trip_t": t_trip, "cooldown_s": cool, "felt": felt, "n_hour": n, "reoffers": int((tr or {}).get("reoffers") or 0)}


def _perma_reoffer(now: float) -> None:
    """The rest is over and the stuck call is back, but her brainstem never took the trip's flinch (it expired, or the link was
    full): offer one again, at most every PERMA_REOFFER_S and PERMA_REOFFER_MAX times. Nothing clears until a flinch is FELT."""
    st = _sh()
    with st["mu"]:
        tr = st.get("trip")
        if (not tr or tr.get("cleared") or tr.get("hard") or now - float(tr.get("reoffer_t") or -1e18) < PERMA_REOFFER_S
                or int(tr.get("reoffers") or 0) >= PERMA_REOFFER_MAX):
            return
        tr["reoffer_t"] = now
        tr["reoffers"] = int(tr.get("reoffers") or 0) + 1
    fid = _trip_flinch(now)
    with st["mu"]:
        tr["fid"] = fid
        st["stats"]["perma_reoffer"] = st["stats"].get("perma_reoffer", 0) + 1


def _perma_clear_if_due() -> None:
    """Called first by latch_state(). When _perma_due says so: the latch file is moved ASIDE (never deleted), the clear is logged
    (a clear that cannot be logged does not happen: the file goes back), then the stuck latch ends. Never raises; a reader that
    cannot take the lock simply sees the latch."""
    try:
        st = _sh()
        tr = st.get("trip")
        if (tr is None or tr.get("cleared")) and not os.path.exists(LATCH_FILE):
            return
        if not _CLEAR_LOCK.acquire(False):
            return
        try:
            now = CLOCK.time()
            due, info = _perma_due(now)
            if not due:
                if info.get("reoffer"):
                    _perma_reoffer(now)
                return
            moved = None
            if os.path.exists(LATCH_FILE):
                moved = "%s.selfcleared_%d" % (LATCH_FILE, int(now))
                k = 0
                while os.path.exists(moved):
                    k += 1
                    moved = "%s.selfcleared_%d_%d" % (LATCH_FILE, int(now), k)
                os.replace(LATCH_FILE, moved)
            row = {"t": now, "ev": "clear", "kind": "stuck", "how": "cool-down", "trip_t": info["trip_t"],
                   "rested_s": round(now - info["trip_t"], 3), "cooldown_s": info["cooldown_s"], "felt": info["felt"],
                   "reoffers": info["reoffers"], "n_hour": info["n_hour"], "boot": _BOOT, "pid": os.getpid(), "moved_to": os.path.basename(moved) if moved else None}
            if not _trip_append(row):
                if moved is not None:
                    os.replace(moved, LATCH_FILE)    # it could not be logged: it stays latched
                return
            with st["mu"]:
                st["latch"].pop("stuck", None)
                if st.get("trip"):
                    st["trip"]["cleared"] = True
                st["trip_block"] = None
                st["last_clear"] = {"t": now, "trip_t": info["trip_t"], "felt": info["felt"]}
                st["stats"]["perma_clear"] = st["stats"].get("perma_clear", 0) + 1
            _say("PERMA: touch rested %.0f s and cleared itself (the trip stays counted in %s)" % (now - info["trip_t"],
                                                                                              os.path.basename(TRIPS_FILE)))
        finally:
            _CLEAR_LOCK.release()
    except Exception:
        return


def trip_state(now: Optional[float] = None) -> Dict:
    """perma: numbers for her body sense and the tests -- {'last_clear_t', 'last_trip_t', 'resting', 'hard', 'trips_hour'}.
    Memory first: nothing is read from disk unless a trip of this boot cleared itself within the last minute. Read-only; never raises."""
    now = CLOCK.time() if now is None else float(now)
    out = {"last_clear_t": None, "last_trip_t": None, "resting": False, "hard": False, "trips_hour": 0}
    try:
        st = _sh()
        with st["mu"]:
            lc, tr = st.get("last_clear"), st.get("trip")
        if lc is None and tr is None:
            return out
        if lc:
            out["last_clear_t"] = lc.get("t")
        if tr:
            out.update(last_trip_t=tr.get("t"), hard=bool(tr.get("hard")), resting=not tr.get("cleared"))
        if lc and 0.0 <= now - float(lc.get("t") or 0.0) <= 60.0:      # the log is read only just after a clear (her body line asks often)
            rows, _e = _trip_rows()
            out["trips_hour"] = sum(1 for r in rows or [] if r.get("ev") == "trip" and 0.0 <= now - float(r["t"]) < PERMA_HARD_WINDOW_S)
    except Exception:
        pass
    return out


# ── the switch: state/touch_screen.json -- absent, torn, unknown keys, expired or far 'until', relative allow path,
#    missing / wrong sha = OFF. Her process only ever writes {"on": false} into it (switch_off) ───────────────────────────
_SW_LOCK = threading.Lock()
_SW_CACHE = {"key": None, "data": None, "err": "absent"}


def _switch_raw() -> Tuple[Optional[Dict], str, Optional[Tuple]]:
    try:
        stt = os.stat(SWITCH_FILE)
    except OSError:
        with _SW_LOCK:
            _SW_CACHE.update(key=None, data=None, err="absent")
        return None, "the switch file is absent", None
    key = (stt.st_mtime_ns, stt.st_size)
    with _SW_LOCK:
        if key != _SW_CACHE["key"]:
            try:
                with open(SWITCH_FILE, "rb") as f:
                    d = json.loads(f.read().decode("utf-8-sig"))
                _SW_CACHE.update(key=key, data=(d if isinstance(d, dict) else None),
                                 err=("" if isinstance(d, dict) else "the switch is not an object"))
            except Exception as e:
                _SW_CACHE.update(key=None, data=None, err="the switch is unreadable (%s)" % type(e).__name__)
                return None, _SW_CACHE["err"], None
        return (dict(_SW_CACHE["data"]) if _SW_CACHE["data"] is not None else None), _SW_CACHE["err"], key


def _hex64(v) -> bool:
    return isinstance(v, str) and len(v) == 64 and all(c in "0123456789abcdef" for c in v)


def read_switch(now: Optional[float] = None) -> Dict:
    """{'on': bool, 'why': str, 'data': dict|None, 'key': (mtime, size)|None}. ON only when every rule holds."""
    now = CLOCK.time() if now is None else float(now)
    d, err, key = _switch_raw()
    out = {"on": False, "why": err, "data": d, "key": key}
    if d is None:
        return out
    extra = set(d) - SWITCH_KEYS
    if extra:
        out["why"] = "unknown keys in the switch: %s" % ",".join(sorted(map(str, extra)))[:80]
        return out
    if d.get("on") is not True:
        out["why"] = "the switch says off"
        return out
    if d.get("stage") not in STAGES:
        out["why"] = "no valid stage"
        return out
    if not isinstance(d.get("watched"), bool):
        out["why"] = "'watched' is missing"
        return out
    if d.get("stage") == "T2" and d.get("watched") is not True:
        out["why"] = "stage T2 is watched only"
        return out
    u = d.get("until")
    if d.get("perma") is True:                       # perma (10-21): a permanent arm has NO expiry, and no 'until' at all
        if "until" in d:
            out["why"] = "a permanent switch carries no 'until'"
            return out
    elif isinstance(u, bool) or not isinstance(u, (int, float)):
        out["why"] = "'until' is missing"
        return out
    elif not (now < float(u) <= now + UNTIL_MAX_S):
        out["why"] = "'until' has passed" if float(u) <= now else "'until' is more than 2 h ahead"
        return out
    a = d.get("allow")
    if not isinstance(a, str) or not os.path.isabs(a) or not (len(a) > 2 and a[1] == ":"):
        out["why"] = "the allow path is not absolute"
        return out
    if not _hex64(d.get("allow_sha256")) or not _hex64(d.get("deny_sha256")):
        out["why"] = "a sha pin is missing"
        return out
    g = d.get("gestures")
    if not isinstance(g, list) or not g or not set(g) <= set(TL.GESTURES):
        out["why"] = "no valid gestures"
        return out
    if d.get("by") != "ace":
        out["why"] = "the switch was not written by Ace's tool"
        return out
    bad = _set1c_bad(d)                              # set1c: its keys are optional; a malformed one leaves the layer OFF
    if bad:
        out["why"] = bad
        return out
    out["on"], out["why"] = True, "on"
    return out


def _set1c_bad(d: Dict) -> str:
    """'' when set1c's optional switch keys are absent or well formed; else why the switch fails closed."""
    p = d.get("parallel", [])
    if not isinstance(p, list) or not set(p) <= set(PARALLEL_GESTURES) or not set(p) <= set(d.get("gestures") or []):
        return "'parallel' is not a list of switched-on tap / hold"
    for k in ("who", "channel", "cue", "perma"):      # fold 10-09: 'eyes' is no longer a touch-switch key; set 1d / 1e keys; perma
        if k in d and not isinstance(d[k], bool):
            return "'%s' is not true / false" % k
    if p and d.get("who") is False:
        return "'who' cannot be off while parallel play is on (Ace 10-09: the efference attribution is not optional)"
    if p and d.get("channel") is not True:           # set 1d (verify S1): parallel play goes over her own channel, never UIA
        return "'parallel' needs 'channel' (set 1d: parallel play never uses Windows' UIA path)"
    if d.get("cue") is True and d.get("channel") is not True:   # set 1e: her cue is drawn by her Playroom, over her channel
        return "'cue' needs 'channel' (set 1e: her finger cue is drawn by her Playroom, over her own channel)"
    if p and d.get("cue") is not True:               # set 1e (P1): probe F9c 10-13 -- her strip / marker windows took his focus
        return "'parallel' needs 'cue' (set 1e: in parallel play her reach shows only inside her Playroom, never in a window)"
    ps = d.get("park_s", 0.0)
    if isinstance(ps, bool) or not isinstance(ps, (int, float)) or not (0.0 <= float(ps) <= PARK_MAX_S):
        return "'park_s' is not a number of seconds from 0 to %.0f" % PARK_MAX_S
    if d.get("perma") is True and (d.get("stage") != "T1" or d.get("watched") is not True):   # perma (10-21): the Playroom, watched
        return "a permanent arm is for the Playroom (stage T1) and watched"
    if "cooldown_s" in d:                            # perma (10-21): how long a stuck trip rests (clamped when it is used)
        c = d["cooldown_s"]
        if d.get("perma") is not True:
            return "'cooldown_s' needs 'perma' (it is how long a permanent arm's stuck trip rests)"
        if isinstance(c, bool) or not isinstance(c, (int, float)) or c != c:
            return "'cooldown_s' is not a number of seconds"
    return ""


def knobs(sw: Optional[Dict] = None) -> Dict:
    """set1c's knobs from a VALID switch; all OFF when the switch is off or carries none of them (= set 1, unchanged)."""
    off = {"on": False, "parallel": frozenset(), "who": False, "park_s": 0.0, "channel": False,   # fold 10-09: no 'eyes'; set 1d
           "cue": False,                                                                          # set 1e
           "perma": False, "cooldown_s": PERMA_COOLDOWN_S}                                        # perma (10-21)
    try:
        sw = read_switch() if sw is None else sw
        if not sw.get("on"):
            return off
        d = sw.get("data") or {}
        par = frozenset(d.get("parallel") or ()) & PARALLEL_GESTURES & frozenset(d.get("gestures") or ())
        return {"on": True, "parallel": par, "who": d.get("who") is True or bool(par),
                "park_s": min(PARK_MAX_S, max(0.0, float(d.get("park_s") or 0.0))),
                "channel": d.get("channel") is True,                 # set 1d
                "cue": d.get("cue") is True and d.get("channel") is True,     # set 1e
                "perma": d.get("perma") is True, "cooldown_s": _perma_cooldown(d)}   # perma (10-21)
    except Exception:
        return off


def switch_off(why: str) -> bool:
    """The ONLY write her process makes to the switch: {"on": false} (a self-pause or a trip)."""
    try:
        tmp = SWITCH_FILE + ".off.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"on": False}, f)
        for _ in range(8):
            try:
                os.replace(tmp, SWITCH_FILE)
                _say("switch written OFF: %s" % why)
                return True
            except PermissionError:
                CLOCK.sleep(0.05)
    except Exception:
        pass
    return False


def stop_present() -> bool:
    return os.path.exists(STOP_FILE)


def deny_sha() -> Optional[str]:
    try:
        with open(TL.__file__, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except Exception:
        return None


def mods_ok() -> Tuple[bool, str]:
    """A hot reload of touch, touch_os, touch_lists or reflex_link is unreviewed code in an actuator: latch OFF."""
    st = _sh()
    for name in _MODS:                                # skeptic M1: importlib.reload keeps the object; the body marks itself
        m = sys.modules.get(name)
        if m is not None and getattr(m, "_RELOADED", False):
            return False, "%s was reloaded in place" % name
    with st["mu"]:
        ids = st["mod_ids"]
        for name in _MODS:
            m = sys.modules.get(name)
            if m is None:
                continue
            if name in ids and ids[name] != id(m):
                return False, "%s was reloaded" % name
            ids.setdefault(name, id(m))
        if (st["imports"].get("infrastructure.touch") or 0) > 1:
            return False, "infrastructure.touch was imported twice"
    if sys.modules.get("infrastructure.touch_lists") is not None and sys.modules["infrastructure.touch_lists"] is not TL:
        return False, "touch_lists in sys.modules is not the one touch_os holds"
    if RL is not None and sys.modules.get("infrastructure.reflex_link") is not None and sys.modules["infrastructure.reflex_link"] is not RL:
        return False, "reflex_link in sys.modules is not the one touch_os holds"
    return True, ""


# ── the allow-list: allow/T<n>.json, typed, stage-bound, class-pinned, sha-pinned; a no-no in it leaves the layer OFF ────
def load_allow(sw: Dict) -> Tuple[Optional[Dict], str]:
    d = sw.get("data") or {}
    path = d.get("allow")
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except Exception:
        return None, "the allow file cannot be read"
    if hashlib.sha256(raw).hexdigest() != d.get("allow_sha256"):
        return None, "the allow file's sha differs from the switch's"
    try:
        a = json.loads(raw.decode("utf-8-sig"))
    except Exception:
        return None, "the allow file is not JSON"
    if not isinstance(a, dict) or set(a) - ALLOW_KEYS:
        return None, "the allow file has unknown keys"
    if a.get("stage") != d.get("stage"):
        return None, "the allow file's stage differs from the switch's"
    stage_cls = STAGE_ROOT_CLASSES.get(a.get("stage"), frozenset())
    roots = a.get("roots")
    if not isinstance(roots, list) or not roots:
        return None, "the allow file names no roots"
    for r in roots:
        if not isinstance(r, dict) or not isinstance(r.get("exe"), str) or not isinstance(r.get("class"), str):
            return None, "a root is not {exe, class}"
        if r["class"] not in stage_cls:
            return None, "root class %s is outside stage %s" % (r["class"], a.get("stage"))
        f = TL.no_no(pid=-1, exe=r["exe"], win_class=r["class"], integrity="medium", phase="load",
                     ctx={"playroom_pid": (-1 if r["class"] in PLAYROOM_CLASSES else None)})
        if f is not None:
            return None, "the allow file names a no-no root (%s: %s)" % (f.cls, f.rule)
    for key in ("items", "menu_rows", "expand_only"):
        v = a.get(key, [])
        if not isinstance(v, list):
            return None, "%s is not a list" % key
        for it in v:
            nm = it.get("name") if isinstance(it, dict) else it
            if not isinstance(nm, str) or not nm.strip():
                return None, "an unnamed entry in %s" % key
            r = TL.name_rule(nm)
            if r is not None:
                return None, "the allow file names a no-no (%s: %s)" % (r[0], nm)
            if isinstance(it, dict):
                gs = it.get("gestures", [])
                if not isinstance(gs, list) or not set(gs) <= set(TL.GESTURES):
                    return None, "bad gestures for %s" % nm
    return a, ""


# ── Win32: ONLY through _u32() ─────────────────────────────────────────────────────────────────────────────────────────────
class _RealWin32:
    """Read-only Win32 facts in PHYSICAL pixels (WindowFromPhysicalPoint, GetPhysicalCursorPos: DESIGN 2f). No call here
    sends input or a message to another window."""

    def __init__(self):
        import ctypes
        import ctypes.wintypes as wt
        self.ct, self.wt = ctypes, wt
        self.u = ctypes.WinDLL("user32", use_last_error=True)
        self.k = ctypes.WinDLL("kernel32", use_last_error=True)
        self.a = ctypes.WinDLL("advapi32", use_last_error=True)
        self.u.WindowFromPhysicalPoint.restype = wt.HWND
        self.u.WindowFromPhysicalPoint.argtypes = [wt.POINT]
        self.u.GetAncestor.restype = wt.HWND
        self.u.GetAncestor.argtypes = [wt.HWND, wt.UINT]
        self.u.GetForegroundWindow.restype = wt.HWND
        self.u.GetWindow.restype = wt.HWND
        self.u.GetWindow.argtypes = [wt.HWND, wt.UINT]
        self.u.GetTopWindow.restype = wt.HWND
        self.u.GetTopWindow.argtypes = [wt.HWND]
        self.u.FindWindowExW.restype = wt.HWND
        self.u.FindWindowExW.argtypes = [wt.HWND, wt.HWND, wt.LPCWSTR, wt.LPCWSTR]
        self.u.MonitorFromPoint.restype = wt.HMONITOR
        self.u.MonitorFromPoint.argtypes = [wt.POINT, wt.DWORD]
        self.k.GetTickCount.restype = wt.DWORD
        # skeptic B1 (10-05): every handle / pointer return is typed. Untyped, ctypes' default c_int cut the 64-bit pointer from
        # GetSidSubAuthorityCount and the next read crashed the whole process (exit 139, reproduced). These are this object's
        # OWN WinDLL instances: nothing else in her process shares these function pointers.
        self.k.OpenProcess.restype = wt.HANDLE
        self.k.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
        self.k.CloseHandle.restype = wt.BOOL
        self.k.CloseHandle.argtypes = [wt.HANDLE]
        self.a.OpenProcessToken.restype = wt.BOOL
        self.a.OpenProcessToken.argtypes = [wt.HANDLE, wt.DWORD, ctypes.POINTER(wt.HANDLE)]
        self.a.GetTokenInformation.restype = wt.BOOL
        self.a.GetTokenInformation.argtypes = [wt.HANDLE, ctypes.c_int, ctypes.c_void_p, wt.DWORD, ctypes.POINTER(wt.DWORD)]
        self.a.GetSidSubAuthorityCount.restype = ctypes.POINTER(ctypes.c_ubyte)
        self.a.GetSidSubAuthorityCount.argtypes = [ctypes.c_void_p]
        self.a.GetSidSubAuthority.restype = ctypes.POINTER(wt.DWORD)
        self.a.GetSidSubAuthority.argtypes = [ctypes.c_void_p, wt.DWORD]
        self.u.GetDC.restype = wt.HDC
        self.u.GetDC.argtypes = [wt.HWND]
        self.u.ReleaseDC.argtypes = [wt.HWND, wt.HDC]
        self.g = ctypes.WinDLL("gdi32", use_last_error=True)
        self.g.GetPixel.restype = wt.DWORD
        self.g.GetPixel.argtypes = [wt.HDC, ctypes.c_int, ctypes.c_int]
        self.k.GetNamedPipeServerProcessId.restype = wt.BOOL          # set 1d (verify T2): her channel's pipe-owner read
        self.k.GetNamedPipeServerProcessId.argtypes = [wt.HANDLE, ctypes.POINTER(wt.ULONG)]

        class LII(ctypes.Structure):
            _fields_ = [("cbSize", wt.UINT), ("dwTime", wt.DWORD)]

        class MI(ctypes.Structure):
            _fields_ = [("cbSize", wt.DWORD), ("rcMonitor", wt.RECT), ("rcWork", wt.RECT), ("dwFlags", wt.DWORD)]

        class GTI(ctypes.Structure):
            _fields_ = [("cbSize", wt.DWORD), ("flags", wt.DWORD), ("hwndActive", wt.HWND), ("hwndFocus", wt.HWND),
                        ("hwndCapture", wt.HWND), ("hwndMenuOwner", wt.HWND), ("hwndMoveSize", wt.HWND),
                        ("hwndCaret", wt.HWND), ("rcCaret", wt.RECT)]
        self.LII, self.MI, self.GTI = LII, MI, GTI

    def tick(self) -> int:
        return int(self.k.GetTickCount()) & 0xFFFFFFFF

    def last_input_tick(self) -> Optional[int]:
        lii = self.LII()
        lii.cbSize = self.ct.sizeof(self.LII)
        if not self.u.GetLastInputInfo(self.ct.byref(lii)):
            return None
        return int(lii.dwTime) & 0xFFFFFFFF

    def physical_cursor(self) -> Optional[Tuple[int, int]]:
        p = self.wt.POINT()
        if not self.u.GetPhysicalCursorPos(self.ct.byref(p)):
            return None
        return int(p.x), int(p.y)

    def window_at(self, x: int, y: int) -> int:
        return int(self.u.WindowFromPhysicalPoint(self.wt.POINT(int(x), int(y))) or 0)

    def root_of(self, hwnd: int) -> int:
        return int(self.u.GetAncestor(self.wt.HWND(hwnd), 2) or 0)          # GA_ROOT

    def window_pid(self, hwnd: int) -> int:
        pid = self.wt.DWORD(0)
        self.u.GetWindowThreadProcessId(self.wt.HWND(hwnd), self.ct.byref(pid))
        return int(pid.value)

    def window_tid(self, hwnd: int) -> int:
        return int(self.u.GetWindowThreadProcessId(self.wt.HWND(hwnd), None))

    def class_name(self, hwnd: int) -> str:
        b = self.ct.create_unicode_buffer(256)
        self.u.GetClassNameW(self.wt.HWND(hwnd), b, 256)
        return b.value

    def window_text(self, hwnd: int) -> str:
        b = self.ct.create_unicode_buffer(512)
        self.u.GetWindowTextW(self.wt.HWND(hwnd), b, 512)
        return b.value

    def window_rect(self, hwnd: int) -> Optional[List[int]]:
        r = self.wt.RECT()
        if not self.u.GetWindowRect(self.wt.HWND(hwnd), self.ct.byref(r)):
            return None
        return [int(r.left), int(r.top), int(r.right), int(r.bottom)]

    def is_window(self, hwnd: int) -> bool:
        return bool(self.u.IsWindow(self.wt.HWND(hwnd)))

    def is_visible(self, hwnd: int) -> bool:
        return bool(self.u.IsWindowVisible(self.wt.HWND(hwnd)))

    def owner_of(self, hwnd: int) -> int:
        return int(self.u.GetWindow(self.wt.HWND(hwnd), 4) or 0)            # GW_OWNER

    def foreground(self) -> int:
        return int(self.u.GetForegroundWindow() or 0)

    def top_windows(self, cap: int = 2000) -> Optional[List[int]]:
        """The z-order walk (GetTopWindow / GW_HWNDNEXT): no callback thunk in a free-threaded process. A repeated or stale
        handle ends the walk and marks the sense dead (None)."""
        out, seen = [], set()
        h = int(self.u.GetTopWindow(None) or 0)
        while h:
            if h in seen or len(out) >= cap:
                return None
            seen.add(h)
            out.append(h)
            h = int(self.u.GetWindow(self.wt.HWND(h), 2) or 0)              # GW_HWNDNEXT
        return out

    def menu_mode(self, hwnd: int) -> Optional[bool]:
        """GetGUIThreadInfo of the TARGET root's own GUI thread: is it in classic menu mode (GUI_INMENUMODE)?"""
        g = self.GTI()
        g.cbSize = self.ct.sizeof(self.GTI)
        if not self.u.GetGUIThreadInfo(self.window_tid(hwnd), self.ct.byref(g)):
            return None
        return bool(int(g.flags) & 0x4)

    def capture_hwnd(self) -> Optional[int]:
        g = self.GTI()
        g.cbSize = self.ct.sizeof(self.GTI)
        if not self.u.GetGUIThreadInfo(0, self.ct.byref(g)):
            return None
        return int(g.hwndCapture or 0)

    def focus_state(self) -> Dict:
        """set1c, the FOCUS LATCH: the foreground window, its GUI thread, and that thread's active and keyboard-focus windows
        (GetForegroundWindow, GetWindowThreadProcessId, GetGUIThreadInfo). Read-only."""
        fg = int(self.u.GetForegroundWindow() or 0)
        tid = self.window_tid(fg) if fg else 0
        g = self.GTI()
        g.cbSize = self.ct.sizeof(self.GTI)
        if not self.u.GetGUIThreadInfo(tid, self.ct.byref(g)):
            return {"fg": fg, "tid": tid, "active": None, "focus": None, "ok": False}
        return {"fg": fg, "tid": tid, "active": int(g.hwndActive or 0), "focus": int(g.hwndFocus or 0), "ok": True}

    def monitors(self) -> List[List[int]]:
        """Every monitor rect, found WITHOUT a callback: MonitorFromPoint over a grid of the virtual screen."""
        sm = self.u.GetSystemMetrics
        vx, vy, vw, vh = sm(76), sm(77), sm(78), sm(79)
        seen, out = set(), []
        for i in range(9):
            for j in range(9):
                p = self.wt.POINT(int(vx + (i + 0.5) * vw / 9), int(vy + (j + 0.5) * vh / 9))
                h = self.u.MonitorFromPoint(p, 0)                          # MONITOR_DEFAULTTONULL
                if not h or int(h) in seen:
                    continue
                seen.add(int(h))
                mi = self.MI()
                mi.cbSize = self.ct.sizeof(self.MI)
                if self.u.GetMonitorInfoW(h, self.ct.byref(mi)):
                    r = mi.rcMonitor
                    out.append([int(r.left), int(r.top), int(r.right), int(r.bottom)])
        return out

    def taskbars(self) -> List[List[int]]:
        out = []
        for cls in ("Shell_TrayWnd", "Shell_SecondaryTrayWnd"):
            h = None
            for _ in range(8):
                h = self.u.FindWindowExW(None, h, cls, None)
                if not h:
                    break
                r = self.window_rect(int(h))
                if r:
                    out.append(r)
        return out

    def integrity(self, pid: int) -> Optional[str]:
        """The integrity level of a process (read-only token query). None when unreadable -> the no-no reads it as 'hot'."""
        ct, wt = self.ct, self.wt
        hp = self.k.OpenProcess(0x1000, False, int(pid))                    # PROCESS_QUERY_LIMITED_INFORMATION
        if not hp:
            return None
        try:
            ht = wt.HANDLE()
            if not self.a.OpenProcessToken(hp, 0x0008, ct.byref(ht)):       # TOKEN_QUERY
                return None
            try:
                n = wt.DWORD(0)
                self.a.GetTokenInformation(ht, 25, None, 0, ct.byref(n))   # TokenIntegrityLevel
                if n.value <= 0:
                    return None
                buf = ct.create_string_buffer(n.value)
                if not self.a.GetTokenInformation(ht, 25, buf, n, ct.byref(n)):
                    return None
                psid = ct.cast(buf, ct.POINTER(ct.c_void_p))[0]
                if not psid:
                    return None
                pcnt = self.a.GetSidSubAuthorityCount(psid)                 # typed: POINTER(c_ubyte), never a cut int
                if not pcnt or int(pcnt[0]) < 1:
                    return None
                prid = self.a.GetSidSubAuthority(psid, int(pcnt[0]) - 1)
                if not prid:
                    return None
                rid = int(prid[0])
                if rid < 0x1000:
                    return "untrusted"
                if rid < 0x2000:
                    return "low"
                if rid < 0x2100:
                    return "medium"
                if rid < 0x3000:
                    return "medium_plus"
                if rid < 0x4000:
                    return "high"
                return "system"
            finally:
                self.k.CloseHandle(ht)
        finally:
            self.k.CloseHandle(hp)

    def proc(self, pid: int) -> Optional[Dict]:
        try:
            import psutil
            p = psutil.Process(int(pid))
            with p.oneshot():
                return {"exe": os.path.basename(p.exe() or p.name() or ""), "cmdline": " ".join(p.cmdline() or []),
                        "ppid": int(p.ppid()), "create_time": float(p.create_time())}
        except Exception:
            return None

    def self_pids(self) -> List[int]:
        try:
            import psutil
            me = psutil.Process(os.getpid())
            return [me.pid] + [c.pid for c in me.children(recursive=True)]
        except Exception:
            return [os.getpid()]

    def is_zoomed(self, hwnd: int) -> Optional[bool]:
        """fold 10-09 (DIAGNOSIS C10 / 5.4, F0's touch part): IsZoomed -- Windows calls the window MAXIMISED. Read-only."""
        try:
            return bool(self.u.IsZoomed(self.wt.HWND(hwnd)))
        except Exception:
            return None

    def is_fullscreen(self, hwnd: int) -> bool:
        r = self.window_rect(hwnd)
        if not r:
            return False
        for m in self.monitors():
            if r[0] <= m[0] and r[1] <= m[1] and r[2] >= m[2] and r[3] >= m[3]:
                return self.class_name(hwnd) not in DESKTOP_CLASSES
        return False

    def dpi_ok(self) -> Tuple[bool, str]:
        """Arm-time gate: GetSystemMetrics(SM_CXSCREEN) in this process must equal the primary monitor's physical width."""
        try:
            ct = self.ct

            class DM(ct.Structure):
                _fields_ = [("dmDeviceName", ct.c_wchar * 32), ("dmSpecVersion", ct.c_ushort), ("dmDriverVersion", ct.c_ushort),
                            ("dmSize", ct.c_ushort), ("dmDriverExtra", ct.c_ushort), ("dmFields", ct.c_ulong),
                            ("dmPosX", ct.c_long), ("dmPosY", ct.c_long), ("dmDisplayOrientation", ct.c_ulong),
                            ("dmDisplayFixedOutput", ct.c_ulong), ("dmColor", ct.c_short), ("dmDuplex", ct.c_short),
                            ("dmYResolution", ct.c_short), ("dmTTOption", ct.c_short), ("dmCollate", ct.c_short),
                            ("dmFormName", ct.c_wchar * 32), ("dmLogPixels", ct.c_ushort), ("dmBitsPerPel", ct.c_ulong),
                            ("dmPelsWidth", ct.c_ulong), ("dmPelsHeight", ct.c_ulong), ("dmDisplayFlags", ct.c_ulong),
                            ("dmDisplayFrequency", ct.c_ulong), ("rest", ct.c_ulong * 8)]
            dm = DM()
            dm.dmSize = ct.sizeof(DM)
            if not self.u.EnumDisplaySettingsW(None, -1, ct.byref(dm)):       # ENUM_CURRENT_SETTINGS
                return False, "display settings unreadable"
            cx = int(self.u.GetSystemMetrics(0))
            return (cx == int(dm.dmPelsWidth)), "SM_CXSCREEN %d vs physical %d" % (cx, int(dm.dmPelsWidth))
        except Exception as e:
            return False, "dpi check raised %s" % type(e).__name__

    def heartbeat_pixel(self, x: int, y: int) -> Optional[Tuple[int, int, int]]:
        """W4's heartbeat read: one pixel of the screen (GetPixel on the screen DC; read-only)."""
        try:
            dc = self.u.GetDC(None)
            if not dc:
                return None
            try:
                c = int(self.g.GetPixel(dc, int(x), int(y))) & 0xFFFFFFFF
            finally:
                self.u.ReleaseDC(None, dc)
            if c == 0xFFFFFFFF:
                return None
            return (c & 0xFF, (c >> 8) & 0xFF, (c >> 16) & 0xFF)
        except Exception:
            return None

    def pipe_server_pid(self, handle) -> Optional[int]:
        """set 1d (verify T2): the process id of a named pipe's SERVER end (GetNamedPipeServerProcessId) -- her channel's
        owner check, read through this accessor like every other OS read. Read-only. None when unreadable."""
        v = self.wt.ULONG(0)
        if not self.k.GetNamedPipeServerProcessId(self.wt.HANDLE(int(handle)), self.ct.byref(v)):
            return None
        return int(v.value)


def _u32():
    st = _sh()
    with st["mu"]:
        w = st.get("win32")
        if w is None:
            w = st["win32"] = _RealWin32()
        return w


# ── UIA: ONLY through _uia(), ONLY on the touch-worker thread ──────────────────────────────────────────────────────────────
class _RealUIA:
    """CUIAutomation8 in the MULTITHREADED apartment, created ON the touch-worker; every element pointer stays local to that
    thread and is dropped before a request returns (comtypes' __del__ calls Release; in 3.14t a finalizer may run anywhere)."""
    PATTERN = {"Select": 10010, "RemoveFromSelection": 10010, "Invoke": 10000, "Expand": 10005, "WindowClose": 10009}
    AVAIL = {"SelectionItem": 30036, "Invoke": 30031, "ExpandCollapse": 30028, "Window": 30044, "LegacyIAccessible": 30090}

    def __init__(self):
        # skeptic m1: comtypes initialises COM on the thread that FIRST imports it, as STA unless sys.coinit_flags says
        # otherwise; then the MTA call below raised RPC_E_CHANGED_MODE (measured). When this worker is the first importer it
        # asks for MTA itself (0 = COINIT_MULTITHREADED) and the process-wide flag is put back at once.
        first = "comtypes" not in sys.modules
        had, old = hasattr(sys, "coinit_flags"), getattr(sys, "coinit_flags", None)
        if first:
            sys.coinit_flags = 0
        try:
            import comtypes
            import comtypes.client
        finally:
            if first:
                if had:
                    sys.coinit_flags = old
                else:
                    try:
                        del sys.coinit_flags
                    except AttributeError:
                        pass
        comtypes.CoInitializeEx(comtypes.COINIT_MULTITHREADED)
        from comtypes.gen import UIAutomationClient as U
        self.U = U
        a = comtypes.client.CreateObject("{e22ad333-b25f-460c-83d0-0581107395c9}", interface=U.IUIAutomation)   # CUIAutomation8
        a2 = a.QueryInterface(U.IUIAutomation2)
        a2.TransactionTimeout = UIA_TRANSACTION_MS
        self.auto = a2

    def element_at(self, x: int, y: int):
        from ctypes.wintypes import POINT
        return self.auto.ElementFromPoint(POINT(int(x), int(y)))

    def info(self, el) -> Dict:
        r = el.CurrentBoundingRectangle
        pats = [k for k, pid in self.AVAIL.items() if bool(el.GetCurrentPropertyValue(pid))]
        d = {"rid": list(el.GetRuntimeId() or ()), "name": str(el.CurrentName or ""),
             "ctype": UIA_CTYPES.get(int(el.CurrentControlType), str(int(el.CurrentControlType))),
             "rect": [int(r.left), int(r.top), int(r.right), int(r.bottom)], "pid": int(el.CurrentProcessId),
             "offscreen": bool(el.CurrentIsOffscreen), "enabled": bool(el.CurrentIsEnabled),
             "class_name": str(el.CurrentClassName or ""), "automation_id": str(el.CurrentAutomationId or ""),
             "patterns": pats, "selected": None}
        if "SelectionItem" in pats:
            try:
                p = el.GetCurrentPattern(10010).QueryInterface(self.U.IUIAutomationSelectionItemPattern)
                d["selected"] = bool(p.CurrentIsSelected)
            except Exception:
                d["selected"] = None
        return d

    def call(self, name: str, el) -> None:
        U = self.U
        if name == "ShowContextMenu":
            el.QueryInterface(U.IUIAutomationElement3).ShowContextMenu()
            return
        if name not in self.PATTERN:
            raise ValueError("not a touch call: %s" % name)
        raw = el.GetCurrentPattern(self.PATTERN[name])
        if name in ("Select", "RemoveFromSelection"):
            p = raw.QueryInterface(U.IUIAutomationSelectionItemPattern)
            (p.Select if name == "Select" else p.RemoveFromSelection)()
        elif name == "Invoke":
            raw.QueryInterface(U.IUIAutomationInvokePattern).Invoke()
        elif name == "Expand":
            raw.QueryInterface(U.IUIAutomationExpandCollapsePattern).Expand()
        elif name == "WindowClose":
            raw.QueryInterface(U.IUIAutomationWindowPattern).Close()


def _uia():
    st = _sh()
    u = st.get("uia")
    if u is None:
        u = st["uia"] = _RealUIA()
    return u


# ── input channels: the hook's physical stamp (decision T12, motor_cortex_fairy) and GetLastInputInfo ─────────────────────
def _wrap_ms(a: int, b: int) -> int:
    """a - b on the 32-bit GetTickCount circle, as a signed number of ms."""
    d = (int(a) - int(b)) & 0xFFFFFFFF
    return d - 0x100000000 if d >= 0x80000000 else d


def channels() -> Dict:
    """{'ok', 'why', 'n', 'phys_n', 'phys_tick', 'any_tick', 'inj', 'inj_marked', 'lii', 'tick', 'hook_alive'}."""
    w = _u32()
    tick = w.tick()
    lii = w.last_input_tick()
    m = sys.modules.get("_sour_council_shared")
    ti = getattr(m, "TOUCH_INPUT", None) if m is not None else None
    out = {"ok": False, "why": "", "lii": lii, "tick": tick, "hook_alive": False}
    if not isinstance(ti, dict):
        out["why"] = "the physical-input stamp is not installed or has seen no input yet (decision T12)"
        return out
    out.update(n=int(ti.get("n") or 0), phys_n=int(ti.get("phys_n") or 0), phys_tick=ti.get("phys_tick"),
               any_tick=ti.get("any_tick"), inj=int(ti.get("inj") or 0), inj_marked=int(ti.get("inj_marked") or 0))
    if lii is None:
        out["why"] = "GetLastInputInfo failed"
        return out
    at = out.get("any_tick")
    # the hook is dead when GetLastInputInfo saw input the hook has NOT seen, and 2 s have passed since that input (S4,
    # FS12.7). A hook a few ms behind the input clock (the two are updated on different threads) is alive, not dead.
    if at is None or (_wrap_ms(lii, int(at)) > 0 and _wrap_ms(tick, lii) > HOOK_DEAD_MS):
        out["why"] = "the hook is dead: input it has not seen, %s ms ago" % (_wrap_ms(tick, lii) if at is not None else "?")
        return out
    out["hook_alive"], out["ok"], out["why"] = True, True, "ok"
    return out


def ace_waiting_live() -> bool:
    m = sys.modules.get("_sour_council_shared")
    if m is None:
        return False
    try:
        if len(getattr(m, "ACE_QUEUE", ()) or ()) > 0:
            return True
        b = float((getattr(m, "ACE_BUSY", None) or [0.0])[0] or 0.0)
        return b > 0.0 and (CLOCK.time() - b) < 300.0
    except Exception:
        return True                                  # unknown = Ace may be waiting: defer


# ── the Playroom's identity (a title alone is spoofable) ──────────────────────────────────────────────────────────────────
def verify_playroom() -> Tuple[Optional[Dict], str]:
    try:
        with open(PLAYROOM_RUN, "rb") as f:
            pr = json.loads(f.read().decode("utf-8"))
    except Exception:
        return None, "the Playroom is not open"
    w = _u32()
    try:
        pid, hwnd = int(pr.get("pid")), int(pr.get("hwnd"))
    except Exception:
        return None, "the Playroom's run file is torn"
    if CLOCK.time() - float(pr.get("heartbeat") or 0.0) > 2.0:
        return None, "the Playroom's heartbeat is stale"
    p = w.proc(pid)
    if not p:
        return None, "the Playroom's process is gone"
    cl = p["cmdline"].replace("/", "\\").lower()
    s1e = PLAYROOM_SCRIPT_TAIL_1E.replace("/", "\\").lower() in cl         # set 1e: + her finger cue drawn inside it
    s1d = s1e or PLAYROOM_SCRIPT_TAIL_1D.replace("/", "\\").lower() in cl  # set 1d: the Playroom with her own channel
    if not s1d and PLAYROOM_SCRIPT_TAIL.replace("/", "\\").lower() not in cl:
        return None, "that process is not the Playroom script"
    if not w.is_window(hwnd) or w.class_name(hwnd) != PLAYROOM_WND or w.window_text(hwnd) != PLAYROOM_TITLE:
        return None, "the Playroom window is not the Playroom's own class and title"
    if w.window_pid(hwnd) != pid:
        return None, "the Playroom window belongs to another process"
    pr["pid"], pr["hwnd"] = pid, hwnd
    pr["set1d"] = bool(s1d)                          # set 1d: only this Playroom's channel is ever trusted
    pr["set1e"] = bool(s1e)                          # set 1e: only this Playroom is ever sent her cue
    return pr, ""


# ── the Win32 facts at a PHYSICAL point (no UIA): LAND step 1-2 and guard step 5 ──────────────────────────────────────────
def facts_at(pt) -> Dict:
    w = _u32()
    x, y = int(pt[0]), int(pt[1])
    f = {"point": [x, y], "dead": None}
    try:
        h = w.window_at(x, y)
        if not h:
            f["dead"] = "no window at the point"
            return f
        root = w.root_of(h) or h
        pid = w.window_pid(root)
        f.update(hwnd=h, root=root, pid=pid, point_class=w.class_name(h), win_class=w.class_name(root),
                 title=w.window_text(root), integrity=w.integrity(pid))
        p = w.proc(pid) or {}
        f.update(exe=p.get("exe"), cmdline=p.get("cmdline") or "", ppid=p.get("ppid"), create_time=p.get("create_time"))
        if not f.get("exe"):
            f["dead"] = "the process at the point is unreadable"
        fg = w.foreground()
        fg_root = w.root_of(fg) if fg else 0
        f["fg_root"] = fg_root
        f["fg_class"] = w.class_name(fg_root) if fg_root else ""
        f["fg_fullscreen"] = bool(fg_root) and w.is_fullscreen(fg_root)
        fgp = w.proc(w.window_pid(fg_root)) if fg_root else None
        f["fg_exe"] = (fgp or {}).get("exe") or ""
        f["monitors"] = w.monitors()
        f["taskbars"] = w.taskbars()
        f["self_pids"] = w.self_pids()
        if not f["monitors"]:
            f["dead"] = "no screen geometry"
    except Exception as e:
        f["dead"] = "a Win32 read raised %s" % type(e).__name__
    return f


def covered(f: Dict) -> bool:
    """Her own strip or marker lies over the point: a deferral, never a miss and never a flinch (FS12.4)."""
    return f.get("pid") in set(f.get("self_pids") or ()) and f.get("win_class") == "TkTopLevel"


def no_no_at(f: Dict, item, gesture: str, phase: str, playroom_pid: Optional[int]):
    """touch_lists.no_no on the facts at the point (and the item)."""
    _fullscreen_note(f, phase)                       # fold 10-09 (DIAGNOSIS 5.4): observation only, behind eyes_fix 'log'
    ctx = {"self_pids": f.get("self_pids") or (), "playroom_pid": playroom_pid, "cmdline": f.get("cmdline"),
           "monitors": f.get("monitors"), "taskbars": f.get("taskbars"), "point": f.get("point"),
           "point_class": f.get("point_class"), "fullscreen_fg": f.get("fg_fullscreen"), "dead_sense": f.get("dead")}
    if f.get("dead"):
        return TL.no_no(item=item, gesture=gesture, phase=phase, ctx=ctx)
    return TL.no_no(root={}, pid=f.get("pid"), exe=f.get("exe"), win_class=f.get("win_class"), integrity=f.get("integrity"),
                    item=item, rect=(item or {}).get("rect") if isinstance(item, dict) else None, gesture=gesture,
                    phase=phase, ctx=ctx)


def call_for(gesture: str, el: Dict, kind: str) -> Optional[str]:
    """The ONE OS call a gesture maps to (DESIGN 2c), or None (refused)."""
    ct = el.get("ctype")
    pats = set(el.get("patterns") or ())
    if "LegacyIAccessible" in pats and not (pats - {"LegacyIAccessible"}):
        return None
    if gesture == "tap":
        if ct in SELECTABLE_CTYPES and "SelectionItem" in pats:
            return "Select"
        if ct == "Button" and "Invoke" in pats and kind == "playroom":
            return "Invoke"
        return None
    if gesture == "double_tap":
        return "Invoke" if (ct == "ListItem" and "Invoke" in pats) else None
    if gesture == "hold":
        return "ShowContextMenu"
    return None


def not_yet(f: Dict, el: Dict, gesture: str, allow: Dict, pr: Optional[Dict], menu_ok: bool, layout_names=()) -> Optional[str]:
    """NOT-YET (Ace's boundaries; never a flinch). None = allowed so far."""
    roots = [(str(r.get("exe", "")).lower(), r.get("class")) for r in (allow.get("roots") or [])]
    wc = f.get("win_class")
    if (str(f.get("exe") or "").lower(), wc) not in roots:
        return "that is not for touching yet (not on the stage's list)"
    if wc in PLAYROOM_CLASSES:
        if not pr or f.get("pid") != pr.get("pid"):
            return "that is not the Playroom"
        if wc == PLAYROOM_MENU and not menu_ok:
            return "that menu is not one you opened"
    ct = el.get("ctype")
    if ct in TL.NOT_YET_CTYPES:
        return "that is not something your fingers press yet"
    if ct in TL.NO_CALL_CTYPES:
        return "nothing there to press"
    nm = el.get("name") or ""
    names = {str(i.get("name") if isinstance(i, dict) else i): i for i in (allow.get("items") or [])}
    rows = set(str(r.get("name") if isinstance(r, dict) else r) for r in (allow.get("menu_rows") or []))
    if wc == PLAYROOM_MENU:
        if nm not in rows:
            return "that is not for touching yet"
    else:
        it = names.get(nm)
        if it is None:
            return "that is not for touching yet"
        gs = it.get("gestures") if isinstance(it, dict) else None
        if gs is not None and gesture not in gs:
            return "that is not for touching that way yet"
    if wc in PLAYROOM_CLASSES and layout_names and nm not in set(layout_names):
        return "that is not one of the Playroom's named things"
    call = call_for(gesture, el, "playroom" if wc in PLAYROOM_CLASSES else "desktop")
    if call is None:
        return "that is not something your fingers press that way"
    host = f.get("point_class") or ""
    if not TL.cleared(call, f.get("exe"), host):
        return "that touch is not proven clean yet (%s on %s is not cleared)" % (call, host or "?")
    return None


# ── the guard: on the WORKER, immediately before the call ─────────────────────────────────────────────────────────────────
def _refuse(kind: str, why: str, **kw) -> Dict:
    d = {"pressed": False, "kind": kind, "why": why}
    d.update(kw)
    return d


def _door_nonce() -> Optional[str]:
    hd = sys.modules.get("infrastructure.hand_door")
    if hd is None:
        return None
    try:
        return hd._st().get("nonce")
    except Exception:
        return None


def guard(req: Dict, recheck: bool = False) -> Optional[Dict]:
    """None = every check passed; else a refusal dict. recheck=True runs steps 1, 2 and 4-7 only (the deadline re-run)."""
    now = CLOCK.time()
    # 0. the door's claim: this request belongs to the deed that holds the hand right now (a re-entrancy check, said honestly)
    if not req.get("nonce") or req.get("nonce") != _door_nonce():
        return _refuse("deferred", "no claim on the hand (the door's nonce)")
    # 1. STOP, the switch, the stage, the lane, the allow file
    if stop_present():
        return _refuse("off", "the STOP file is there")
    sw = read_switch(now)
    if not sw["on"]:
        return _refuse("off", "touch is off: %s" % sw["why"])
    d = sw["data"]
    if req.get("gesture") not in d.get("gestures", []):
        return _refuse("not_yet", "that gesture is not switched on")
    if req.get("lane") not in SET1_LANES:
        return _refuse("not_yet", "that lane does not touch yet")
    if req.get("stage") != d.get("stage"):
        return _refuse("off", "the stage changed")
    allow, why = load_allow(sw)
    if allow is None:
        return _refuse("off", why)
    # 2. latches (memory and disk); 2b her brainstem beating (read ONLY in the closed direction)
    lt, reasons = latch_state()
    if lt:
        return _refuse("off", "latched: %s" % ", ".join("%s (%s)" % kv for kv in reasons.items())[:160])
    if RL is None:
        return _refuse("off", "reflex_link is missing")
    ok, why = RL.alive(now)
    if not ok:
        if why in ("two_beaters", "beater_changed"):     # skeptic S6: a takeover never heals by waiting 30 s
            latch("beaters", "two brainstems beating" if why == "two_beaters" else "the beating brainstem changed")
            return _refuse("off", "two brainstems are beating" if why == "two_beaters" else "the beating brainstem changed")
        return _refuse("deferred", "your reflex is not awake (%s)" % why)
    # 3. the no-no module's pin; no hot reload
    if not recheck:
        if deny_sha() != d.get("deny_sha256"):
            latch("sha", "touch_lists sha differs from the switch's pin")
            return _refuse("off", "the no-no list is not the pinned one")
        mok, mwhy = mods_ok()
        if not mok:
            latch("reload", mwhy)
            return _refuse("off", mwhy)
    # 4. Ace first, and his veto: nothing moved since the announce began
    ch = channels()
    if not ch["ok"]:
        if "dead" in ch["why"]:
            switch_off(ch["why"])                     # a dead hook turns the layer OFF (DESIGN 8); Ace re-arms with touch_on
        return _refuse("off", ch["why"])
    if ace_waiting_live():
        return _refuse("deferred", "Ace is waiting for an answer")
    an = req.get("announce") or {}
    if an.get("phys_n") is None or an.get("lii") is None:
        return _refuse("deferred", "no announce on record")
    if req.get("parallel"):                           # set1c PARALLEL PLAY: HIS ROOM is the veto, not his hands elsewhere
        pv = parallel_guard(req, d)
        if pv is not None:
            return pv
        ch = dict(ch, phys_n=an["phys_n"], lii=an["lii"])   # his input ELSEWHERE is no veto: the strict reads below see the
                                                            # announce by design (his room, its own log and the focus ran above)
    if ch["phys_n"] != an["phys_n"] or ch["lii"] != an["lii"]:
        return _refuse("deferred", "Ace's hand moved during the announce", reason="ace_veto")
    floor = _idle_floor(req, d)
    idle_ms = _wrap_ms(ch["tick"], ch["lii"])
    if idle_ms < floor * 1000.0:
        return _refuse("deferred", "Ace touched the PC %.1f s ago (floor %.0f s)" % (idle_ms / 1000.0, floor), reason="ace_first")
    # 5. the no-no, authoritative, on the facts at the point NOW (and the menu row Y of a compound hold)
    f = facts_at(req["point"])
    pr, _w = verify_playroom()
    pr_pid = pr.get("pid") if pr else None
    if (str(f.get("fg_exe") or "").lower() in PAUSE_EXES or f.get("fg_fullscreen")
            or (not f.get("fg_root") and not f.get("dead"))):
        return _refuse("deferred", "the whole layer pauses (a game, the lock screen or no foreground)")
    if covered(f):
        return _refuse("deferred", "your strip was over it", reason="covered")
    item = dict(req.get("aim") or {})
    fl = no_no_at(f, {"name": item.get("name"), "automation_id": item.get("automation_id"), "rect": item.get("rect"),
                      "call": req.get("call")}, req.get("gesture"), "guard", pr_pid)
    if fl is None and req.get("then_item"):           # Y of a compound hold, on the SAME facts (its row is in the Playroom's
        fl = no_no_at(f, {"name": req["then_item"]}, req.get("gesture"), "guard", pr_pid)   # own menu): a name rule, not 'unknown'
    if fl is not None:
        return _refuse("withdrawn", fl.rule, flinch=TL.flinch_dict(fl, reach_frac=1.0, stop_px=0, t=now))
    # foreground rule on the real desktop (S5): double_tap / hold only with the desktop or an allow-listed root in front
    if req.get("kind") == "desktop" and req.get("gesture") in ("double_tap", "hold"):
        roots = {r.get("class") for r in allow.get("roots") or []}
        if f.get("fg_class") not in DESKTOP_CLASSES and f.get("fg_class") not in roots:
            return _refuse("deferred", "another app is in front: Ace may be there", reason="ace_first")
    # 6. NOT-YET -- the stage's roots FIRST: never a UIA read on a window the stage does not list (skeptic S9, as LAND does)
    roots = [(str(r.get("exe", "")).lower(), r.get("class")) for r in (allow.get("roots") or [])]
    if (str(f.get("exe") or "").lower(), f.get("win_class")) not in roots:
        return _refuse("not_yet", "that is not for touching yet (not on the stage's list)")
    el = _read_element(req["point"])
    if el is None:
        return _refuse("unverified", "the item could not be read")
    ny = not_yet(f, el, req.get("gesture"), allow, pr, bool(req.get("menu_ok")), req.get("layout_names") or ())
    if ny:
        return _refuse("not_yet", ny)
    # 7. identity: RuntimeId AND Name AND ControlType, rect within 4 px; on screen, enabled; same process and root
    if not _same_item(item, el, f):
        return _refuse("moved", "the item changed between the aim and the press")
    if recheck:
        return None
    # 8. rate backstop
    st = _sh()
    with st["mu"]:
        ps = [t for t in st["presses"] if now - t < 86400.0]
        st["presses"] = ps
        if ps and now - ps[-1] < MIN_PRESS_GAP_S:
            return _refuse("deferred", "a press %.1f s ago" % (now - ps[-1]))
        if len(ps) >= DAY_PRESS_CAP:
            return _refuse("deferred", "today's presses are used up")
    if req.get("outstanding_ok") is not True:
        return _refuse("deferred", "something she opened is still open")
    # 10. the call must be on CLEARED_CALLS (probe F1 / F8, 20/20)
    call = req.get("call")
    if call != call_for(req.get("gesture"), el, req.get("kind")) or not TL.cleared(call, f.get("exe"), f.get("point_class")):
        return _refuse("not_yet", "that touch is not proven clean yet")
    # 11. set 1d: HOW the press reaches it -- her Playroom's own channel, Windows' UIA write path, or not at all
    route, rinfo = route_for(req, f, pr, d)
    if route is None:
        return _refuse("deferred", rinfo, reason="channel")
    req["_route"], req["_chan"] = route, (rinfo if route == "channel" else None)
    req["_facts"], req["_el"] = f, el
    return None


def _idle_floor(req: Dict, d: Dict) -> float:
    if req.get("parallel"):                           # set1c: the ROOM's floor ran in parallel_guard (his input elsewhere is not his
        return 0.0                                    # hand in her room)
    if req.get("kind") == "playroom":
        return IDLE_FLOOR_S["playroom"]
    if d.get("watched"):
        return IDLE_FLOOR_S["desktop_watched"]
    return IDLE_FLOOR_S["desktop_tap"] if req.get("gesture") == "tap" else IDLE_FLOOR_S["desktop_open"]


def _same_item(aim: Dict, el: Dict, f: Dict) -> bool:
    try:
        if list(aim.get("rid") or []) != list(el.get("rid") or []) or not aim.get("rid"):
            return False
        if aim.get("name") != el.get("name") or aim.get("ctype") != el.get("ctype"):
            return False
        if any(abs(int(a) - int(b)) > RECT_TOL_PX for a, b in zip(aim.get("rect") or [], el.get("rect") or [])):
            return False
        if len(aim.get("rect") or []) != 4 or len(el.get("rect") or []) != 4:
            return False
        if el.get("offscreen") or not el.get("enabled"):
            return False
        return el.get("pid") == f.get("pid") and aim.get("pid") == f.get("pid") and aim.get("root") in (None, f.get("root"))
    except Exception:
        return False


def _read_element(pt) -> Optional[Dict]:
    """ElementFromPoint + its facts; worker thread only. None on any failure."""
    try:
        u = _uia()
        el = u.element_at(int(pt[0]), int(pt[1]))
        try:
            return u.info(el)
        finally:
            del el
    except Exception:
        _sense_error("element read")
        return None


def _sense_error(what: str) -> None:
    st = _sh()
    now = CLOCK.time()
    with st["mu"]:
        st["sense_errors"] = [t for t in st["sense_errors"] if now - t < 600.0] + [now]
        n = len(st["sense_errors"])
    if n >= 3:
        switch_off("3 UIA sense errors in 10 min (%s)" % what)


# ── the press, on the worker ──────────────────────────────────────────────────────────────────────────────────────────────
def _last_reads(req: Dict) -> Optional[Dict]:
    if stop_present():
        return _refuse("off", "the STOP file is there")
    sw = read_switch()
    if not sw["on"] or sw.get("key") != req.get("switch_key"):
        return _refuse("off", "the switch changed")
    if req.get("parallel"):                           # set1c: his room and the focus latch, not the global channels
        return parallel_reads(req)
    ch = channels()
    an = req.get("announce") or {}
    if not ch["ok"] or ch["phys_n"] != an.get("phys_n") or ch["lii"] != an.get("lii"):
        return _refuse("deferred", "Ace's hand moved", reason="ace_veto")
    return None


def _still_quiet(req: Dict) -> bool:
    """Both input channels exactly as at the announce (the veto), read at the last instant before the call."""
    try:
        if req.get("parallel"):                       # set1c: his room and the focus latch at the last instant
            pr_ = parallel_reads(req)
            if pr_ is not None:
                req["_par_reason"] = pr_.get("reason")
            return pr_ is None
        ch = channels()
        an = req.get("announce") or {}
        return bool(ch["ok"]) and ch.get("phys_n") == an.get("phys_n") and ch.get("lii") == an.get("lii")
    except Exception:
        return False


class _Sentinel:
    """W7 across the call: the PHYSICAL cursor at >= 200 Hz from 50 ms before to 500 ms after, then the input clock and the
    hook's counters before and after. A 50 ms move-and-restore that a before/after pair would miss shows up here."""

    def __init__(self, rest):
        self.rest = tuple(rest) if rest else None
        self.samples = []
        self.stop_ev = threading.Event()
        self.t = None

    def _run(self):
        w = _u32()
        step = 1.0 / SENTINEL_HZ
        while not self.stop_ev.is_set():
            try:
                self.samples.append(w.physical_cursor())
            except Exception:
                self.samples.append(None)
            CLOCK.sleep(step)

    def _one(self):
        try:
            self.samples.append(_u32().physical_cursor())
        except Exception:
            self.samples.append(None)

    def start(self):
        self._one()                                   # one sample is always taken before the call ...
        self.t = threading.Thread(target=self._run, daemon=True, name="touch-sentinel")
        self.t.start()
        CLOCK.sleep(SENTINEL_PRE_S)

    def stop(self):
        CLOCK.sleep(SENTINEL_POST_S)
        self.stop_ev.set()
        if self.t is not None:
            self.t.join(2.0)
        self._one()                                   # ... and one after, so a blind thread can never read as 'clean'

    def in_rect(self, rect) -> int:
        """set1c: samples inside a rect (her room) -- parallel play's sentinel."""
        try:
            return sum(1 for p in self.samples if p is not None and rect[0] <= p[0] < rect[2] and rect[1] <= p[1] < rect[3])
        except Exception:
            return 1

    def moved(self) -> Tuple[int, int]:
        """(samples, samples away from the first sample)."""
        s = [p for p in self.samples if p is not None]
        if not s:
            return 0, 0
        ref = self.rest or s[0]
        return len(s), sum(1 for p in s if abs(p[0] - ref[0]) > 0 or abs(p[1] - ref[1]) > 0)


def _press_on_worker(req: Dict) -> Dict:
    t1 = CLOCK.perf()
    r = guard(req)
    if r is not None:
        return r
    _after_guard()
    if CLOCK.perf() - t1 > DEADLINE_S:
        _bump("deadline_rerun")
        t1 = CLOCK.perf()
        r = guard(req, recheck=True)
        if r is not None:
            return r
        _after_guard()
        if CLOCK.perf() - t1 > DEADLINE_S:
            _bump("deadline_deferred")
            return _refuse("deferred", "the moment passed (100 ms between the checks and the press, twice)")
    r = _last_reads(req)
    if r is not None:
        return r
    w = _u32()
    ch0 = channels()
    cur0 = w.physical_cursor()
    sent = _Sentinel(cur0)
    sent.start()
    tick_call = w.tick()
    err = None
    vetoed = False
    cres = None                                       # set 1d: the channel's answer (None = the UIA path)
    try:
        u = _uia()
        el = u.element_at(int(req["point"][0]), int(req["point"][1]))
        try:
            if u.info(el).get("rid") != req["_el"].get("rid"):
                err = "the item changed at the last instant"
            elif not _still_quiet(req):                # skeptic m2: his hand, compared once more right before the call
                err, vetoed = "Ace's hand moved at the last instant", True
            else:
                st = _sh()
                with st["mu"]:
                    st["presses"].append(CLOCK.time())
                if req.get("_route") == "channel":    # set 1d: her own Playroom does it, inside its own window
                    cres = _channel_press(req)
                else:
                    u.call(req["call"], el)
        finally:
            del el
    except Exception as e:
        err = "%s: %s" % (type(e).__name__, str(e)[:100])
    if vetoed:
        sent.stop()
        return _refuse("deferred", "Ace's hand moved", reason=req.get("_par_reason") or "ace_veto")   # set1c: or focus_latch
    sent.stop()
    ccls = channel_outcome(cres) if (cres is not None and err is None) else None    # set 1d
    if ccls == "not_done":
        err = "your Playroom did not do it (%s)" % str(cres.get("why") or "no reason given")[:100]
    elif ccls == "unsure":
        err = "your Playroom did not say whether it did it (%s)" % str(cres.get("why") or "no answer")[:100]
    ch1 = channels()
    n_s, n_moved = sent.moved()
    out = {"pressed": err is None, "kind": "pressed" if err is None else "failed", "why": err or "pressed",
           "call": req["call"], "tick_call": tick_call, "facts": req.get("_facts"), "before_el": req.get("_el"),
           "sentinel": {"samples": n_s, "moved": n_moved, "lii0": ch0.get("lii"), "lii1": ch1.get("lii"),
                        "phys_n0": ch0.get("phys_n"), "phys_n1": ch1.get("phys_n"), "inj0": ch0.get("inj"),
                        "inj1": ch1.get("inj")}}
    if req.get("_route") == "channel":                # set 1d: it went over her Playroom's channel, and what the Playroom said
        out["via"] = "channel"
    if cres is not None:
        out["channel"] = {"sent": bool(cres.get("sent")), "ok": cres.get("ok"), "why": str(cres.get("why") or "")[:120],
                          "effect": (cres.get("reply") or {}).get("effect") if isinstance(cres.get("reply"), dict) else None,
                          "outcome": ccls}
        if ccls == "not_done":                        # nothing happened (never sent, or the Playroom refused it)
            out.update(kind="deferred", reason="channel", done=False)
        elif ccls == "unsure":                        # it may have happened: never 'did not', never 'you did'
            out.update(kind="failed", reason="channel_unsure")
    v = sentinel_verdict(out["sentinel"]) if not req.get("parallel") else parallel_verdict(out, sent, req)   # set1c
    out["ace_input"] = v in ("ace", "room")
    if v == "violation":
        why = "input she did not make appeared during her call (cursor %d/%d, inj %s->%s, lii %s->%s)" % (
            n_moved, n_s, ch0.get("inj"), ch1.get("inj"), ch0.get("lii"), ch1.get("lii"))
        latch("violation", why)
        out["violation"] = why
    if req.get("parallel"):                           # set1c: the focus latch, read after the call and its 500 ms watch
        parallel_after(req, out)
    return out


def sentinel_verdict(s: Dict) -> str:
    """'clean' | 'ace' (physical input: not hers) | 'violation' (the cursor moved, the clock moved or an injected event came
    with no physical event of Ace's to explain it; or the sentinel saw nothing at all = blind)."""
    if int(s.get("samples") or 0) <= 0:
        return "violation"
    phys = (s.get("phys_n1") or 0) != (s.get("phys_n0") or 0)
    inj = (s.get("inj1") or 0) != (s.get("inj0") or 0)
    lii = s.get("lii1") != s.get("lii0")
    if inj:
        return "violation"
    if (int(s.get("moved") or 0) > 0 or lii) and not phys:
        return "violation"
    if phys:
        return "ace"
    return "clean"


class _Worker:
    def __init__(self):
        self.q = queue.Queue()
        self.pending = 0                              # perma (10-21): requests given and not yet finished; 0 = a stuck call is back
        self.mu = threading.Lock()
        self.t = threading.Thread(target=self._run, daemon=True, name="touch-worker")
        self.t.start()

    def _run(self):
        while True:
            req, box = self.q.get()
            try:
                if req.get("op") == "read":
                    res = _read_on_worker(req)
                else:
                    res = _press_on_worker(req)
            except Exception as e:
                res = _refuse("failed", "the worker raised %s: %s" % (type(e).__name__, str(e)[:80]))
            for k in ("_facts", "_el"):
                req.pop(k, None)
            box["res"] = res
            if box.get("abandoned"):
                st = _sh()
                with st["mu"]:
                    st["late"] += 1
                _say("a stuck call returned late: %s (the layer stays OFF)" % str(res.get("why"))[:80])
                if req.get("op") == "press":          # set1c (verify W3): the late press is her efference too (never 'ok')
                    _efference_late(req, res)
            box["ev"].set()
            with self.mu:                             # perma (10-21): this request is finished (a stuck one too, however late)
                self.pending = max(0, self.pending - 1)

    def submit(self, req: Dict, timeout: float) -> Dict:
        box = {"ev": threading.Event(), "res": None, "abandoned": False}
        with self.mu:                                 # perma (10-21): counted before it is queued
            self.pending += 1
        self.q.put((req, box))
        if not box["ev"].wait(timeout):
            box["abandoned"] = True
            latch("stuck", "a touch call did not return in %.0f s (a dialog may be waiting for Ace)" % timeout)
            return _refuse("deferred", "your finger is held", reason="stuck")
        return box["res"]


def _worker() -> _Worker:
    st = _sh()
    with st["mu"]:
        w = st.get("worker")
        if w is None or not w.t.is_alive():
            w = st["worker"] = _Worker()
        return w


def _read_on_worker(req: Dict) -> Dict:
    """LAND step 4: ElementFromPoint, only after the Win32 pre-check passed (touch.py) -- and re-checked here: never a UIA
    read on a no-no window or a root outside the stage's list."""
    f = facts_at(req["point"])
    pr, _w = verify_playroom()
    fl = no_no_at(f, None, req.get("gesture"), "land", pr.get("pid") if pr else None)
    if fl is not None:
        return {"ok": False, "flinch": TL.flinch_dict(fl)}
    sw = read_switch()
    allow, why = load_allow(sw) if sw["on"] else (None, sw["why"])
    if allow is None:
        return {"ok": False, "why": why}
    roots = {(str(r.get("exe", "")).lower(), r.get("class")) for r in allow.get("roots") or []}
    if (str(f.get("exe") or "").lower(), f.get("win_class")) not in roots:
        return {"ok": False, "why": "not on the stage's list"}
    el = _read_element(req["point"])
    return {"ok": el is not None, "el": el, "facts": f}


def read_at(pt, gesture: str) -> Dict:
    return _worker().submit({"op": "read", "point": list(pt), "gesture": gesture}, WATCHDOG_S)


def press(req: Dict) -> Dict:
    """THE ONE PRESS. Hands the request to the touch-worker, which runs the whole guard again itself and makes at most one
    cleared call. A call that has not returned in 4 s latches 'stuck'."""
    if not isinstance(req, dict) or req.get("op", "press") != "press":
        return _refuse("failed", "not a press request")
    r = dict(req)
    r["op"] = "press"
    t0 = CLOCK.time()
    r["_t0"] = t0                                     # set1c: a press that comes back LATE is still her efference (verify W3)
    res = _worker().submit(r, WATCHDOG_S)
    _efference_note(req, res, t0)                     # set1c (who touched): her own press, exactly as it came back
    return res


# ── after-senses, read-only Win32 (touch.py's WATCH; DESIGN 4b W1, W4, W5) ────────────────────────────────────────────
def tops() -> Optional[List[Dict]]:
    """W1: every top-level window, untitled popups included, as {hwnd, pid, class, owner, rect, visible}; None = dead sense."""
    w = _u32()
    try:
        hs = w.top_windows()
        if hs is None:
            return None
        out = []
        for h in hs:
            if not w.is_visible(h):
                continue
            out.append({"hwnd": h, "pid": w.window_pid(h), "class": w.class_name(h), "owner": w.owner_of(h),
                        "rect": w.window_rect(h)})
        return out
    except Exception:
        return None


def screen_geometry() -> Tuple[List[List[int]], List[List[int]]]:
    w = _u32()
    try:
        return w.monitors(), w.taskbars()
    except Exception:
        return [], []


def heartbeat_read(pr: Optional[Dict]) -> Optional[Tuple[int, int, int]]:
    """W4: the Playroom's heartbeat pixel (it flips colour every second); None when unreadable."""
    try:
        hb = (pr or {}).get("heartbeat_xy")
        if not hb:
            return None
        return _u32().heartbeat_pixel(int(hb[0]), int(hb[1]))
    except Exception:
        return None


def foreground_root() -> int:
    w = _u32()
    try:
        fg = w.foreground()
        return w.root_of(fg) if fg else 0
    except Exception:
        return 0


def rest_cursor() -> Optional[Tuple[int, int]]:
    try:
        return _u32().physical_cursor()
    except Exception:
        return None


# ── set1c (10-09): parallel play, the focus latch, her efference copy, her eyes' toy names (read-only; _u32() only) ────────
def same_focus(a: Optional[Dict], b: Optional[Dict]) -> bool:
    """The FOCUS LATCH's comparison: the foreground window, its GUI thread, its active and keyboard-focus windows, unchanged.
    An unreadable side is a change (nothing runs in parallel on a sense that cannot say)."""
    if not isinstance(a, dict) or not isinstance(b, dict) or not a.get("ok") or not b.get("ok"):
        return False
    return all(a.get(k) == b.get(k) for k in ("fg", "tid", "active", "focus"))


def focus_now() -> Optional[Dict]:
    """{'fg', 'tid', 'active', 'focus', 'ok'}; None when the sense is missing or raised."""
    try:
        f = getattr(_u32(), "focus_state", None)
        return f() if f is not None else None
    except Exception:
        return None


def _room_log() -> Dict:
    st = _sh()
    with st["mu"]:
        rl = st.get("room_log")
        if rl is None:
            rl = st["room_log"] = {"mu": threading.Lock(), "off": None, "rows": [], "err": None, "path": None}
        return rl


def playroom_rows(since: float) -> Optional[List[Dict]]:
    """The Playroom's OWN log (run/playroom_events.jsonl: every mouse / key message that reaches it, as its KIND only, and
    every effect), rows with t >= since. Tailed incrementally (the first read takes the last 64 KB); the last
    ROOM_LOG_KEEP_S kept in memory. None = unreadable (the callers then act as if Ace were in her room)."""
    rl = _room_log()
    now = CLOCK.time()
    with rl["mu"]:
        try:
            if rl["path"] != PLAYROOM_EVENTS:            # (cell tests point the path at their own fake log)
                rl.update(path=PLAYROOM_EVENTS, off=None, rows=[])
            size = os.path.getsize(PLAYROOM_EVENTS)
            first = rl["off"] is None or size < rl["off"]
            if first:
                rl["off"] = max(0, size - ROOM_LOG_TAIL_BYTES)
                rl["rows"] = []
            with open(PLAYROOM_EVENTS, "rb") as f:
                f.seek(rl["off"])
                data = f.read(max(0, size - rl["off"]))
            if first and rl["off"] > 0:                  # a tail read starts inside a line: skip to the next whole one
                j = data.find(b"\n")
                data = data[j + 1:] if j >= 0 else b""
                rl["off"] += (j + 1) if j >= 0 else 0
            i = data.rfind(b"\n")
            chunk = data[:i + 1] if i >= 0 else b""
            rl["off"] += len(chunk)
            for line in chunk.splitlines():
                try:
                    r = json.loads(line.decode("utf-8", "replace"))
                except Exception:
                    continue
                if isinstance(r, dict) and isinstance(r.get("t"), (int, float)):
                    rl["rows"].append(r)
            rl["rows"] = [r for r in rl["rows"] if now - float(r["t"]) <= ROOM_LOG_KEEP_S]
            rl["err"] = None
            return [dict(r) for r in rl["rows"] if float(r["t"]) >= since]
        except Exception as e:
            rl["err"] = type(e).__name__
            return None


def room_kind(r: Dict) -> str:
    """The input KIND of a Playroom log row ('' for an effect or anything else); QUEUE rows are the same message's witness."""
    ev = str(r.get("ev") or "")
    base = ev[6:] if ev.startswith("QUEUE ") else ev
    return base if base in ROOM_INPUT_EVS else ""


def room_state(pr: Optional[Dict] = None) -> Dict:
    """Is Ace IN HER ROOM? in_room = the Playroom (or a window of its process) is his foreground, OR his cursor is over the
    Playroom's rect or over any window of its process, OR a reply to him is pending. idle_ms / last_input_t = his last input
    the Playroom ITSELF saw (its own log). Any sense that cannot say = in_room True (the strict rule decides)."""
    out = {"ok": False, "in_room": True, "why": "", "hwnd": None, "pid": None, "rect": None, "idle_ms": 0.0, "last_input_t": None}
    try:
        if pr is None:
            pr, pwhy = verify_playroom()
            if pr is None:
                out["why"] = pwhy
                return out
        w = _u32()
        hwnd, pid = int(pr["hwnd"]), int(pr["pid"])
        rect = w.window_rect(hwnd)
        if not rect or len(rect) != 4:
            out["why"] = "the Playroom's rect is unreadable"
            return out
        out.update(hwnd=hwnd, pid=pid, rect=[int(v) for v in rect])
        cur = w.physical_cursor()
        if cur is None:
            out["why"] = "the cursor is unreadable"
            return out
        fg = w.foreground()
        fg_root = w.root_of(fg) if fg else 0
        h = w.window_at(cur[0], cur[1])
        root = (w.root_of(h) or h) if h else 0
        under_pid = w.window_pid(root) if root else 0
        inside = rect[0] <= cur[0] < rect[2] and rect[1] <= cur[1] < rect[3]
        fg_room = bool(fg_root) and (fg_root == hwnd or w.window_pid(fg_root) == pid)
        cursor_in = bool(inside or under_pid == pid)
        waiting = ace_waiting_live()
        rows = playroom_rows(CLOCK.time() - ROOM_LOG_KEEP_S)
        if rows is None:
            out["why"] = "the Playroom's own log is unreadable"
            return out
        ts = [float(r["t"]) for r in rows if room_kind(r)]
        last = max(ts) if ts else None
        out.update(ok=True, fg_room=fg_room, cursor_in=cursor_in, waiting=waiting, cursor=[int(cur[0]), int(cur[1])],
                   fg=fg_root, last_input_t=last,
                   idle_ms=(1000.0 * (CLOCK.time() - last)) if last is not None else 1000.0 * ROOM_LOG_KEEP_S)
        out["in_room"] = bool(fg_room or cursor_in or waiting)
        cl = pr.get("client") if pr.get("set1d") is True else None     # set 1d (verify S3): its client area, where its panel lies
        if isinstance(cl, list) and len(cl) == 4:
            out["client"] = [int(v) for v in cl]
        out["why"] = ("the Playroom is in front" if fg_room else "his cursor is over your room" if cursor_in else
                      "a reply to him is pending" if waiting else "clear")
    except Exception as e:
        out["why"] = "a room read raised %s" % type(e).__name__
    return out


def parallel_latched(key) -> bool:
    """The FOCUS LATCH is set for THIS touch session (keyed to the switch Ace wrote): memory, never a file -- the strict rule
    returns and touch stays on; a new touch_on session (a new switch) starts clean; her next boot starts clean."""
    st = _sh()
    with st["mu"]:
        pl = st.get("parallel_latch")
    return bool(pl) and pl.get("key") == key


def parallel_latch(why: str, key) -> None:
    st = _sh()
    with st["mu"]:
        st["parallel_latch"] = {"key": key, "why": str(why)[:200], "t": CLOCK.time()}
        st["stats"]["parallel_latch"] = st["stats"].get("parallel_latch", 0) + 1
    _say("PARALLEL PLAY LATCHED OFF for this touch session: %s -- the strict rule is back (memory, not a file: a new touch_on "
         "session starts clean)" % why)


def parallel_reads(req: Dict, floor: bool = False) -> Optional[Dict]:
    """His room and the focus latch, NOW (the guard with floor=True, the last reads, the last instant). None = clear."""
    room = room_state()
    if not room.get("ok") or room.get("in_room"):
        return _refuse("deferred", "Ace is in your room (%s)" % room.get("why"), reason="ace_veto")
    if room.get("hwnd") != (req.get("room") or {}).get("hwnd"):
        return _refuse("deferred", "the Playroom is not the one she aimed in", reason="ace_veto")
    req["room"] = dict(req.get("room") or {}, rect=list(room["rect"]))   # verify S2: the sentinel judges her room as it is NOW
    mp = req.get("menu")
    if req.get("gesture") == "hold":                  # verify S1: where her menu would open is still all her room, NOW
        ok_m = isinstance(mp, dict) and menu_in_room(room["hwnd"], room["rect"], mp.get("toy_rect"), mp.get("rows"),
                                                     client=room.get("client"))[0]                     # set 1d (verify S3)
        if not ok_m:
            return _refuse("deferred", "its menu would open over one of Ace's windows", reason="ace_first")
    if floor and float(room.get("idle_ms") or 0.0) < IDLE_FLOOR_S["playroom"] * 1000.0:
        return _refuse("deferred", "Ace's hand was in your room %.1f s ago" % (float(room["idle_ms"]) / 1000.0), reason="ace_first")
    f = focus_now()
    if f is None or not f.get("ok"):
        return _refuse("deferred", "the focus could not be read", reason="ace_first")
    if not same_focus(f, req.get("focus0")):
        parallel_latch("the foreground or keyboard focus changed before her press", req.get("switch_key"))
        return _refuse("deferred", "the focus moved while your finger was out", reason="focus_latch")
    return None


def parallel_guard(req: Dict, d: Dict) -> Optional[Dict]:
    """Guard step 4 for a parallel press: the gesture plays in parallel, the latch is not set, his room is clear (and quiet for
    the Playroom's floor by its own log), the focus is the one read before anything of hers showed."""
    kn = knobs({"on": True, "data": d})
    if req.get("gesture") not in kn["parallel"] or req.get("kind") != "playroom":
        return _refuse("deferred", "parallel play is not on for that", reason="ace_first")
    if parallel_latched(req.get("switch_key")):
        return _refuse("deferred", "parallel play is off for this session", reason="ace_first")
    return parallel_reads(req, floor=True)


def parallel_verdict(out: Dict, sent, req: Dict) -> str:
    """The sentinel for a parallel press: the strict verdict first (blind / injected / a move or a clock change with no hand
    of his = violation, latched as set 1 does); then his hands ELSEWHERE are expected ('clean'), but a cursor sample INSIDE her
    room is 'room' (his hand or hers: it cannot be told -> not hers, and the latch trips)."""
    v = sentinel_verdict(out["sentinel"])
    if v == "violation":
        return v
    rect = (req.get("room") or {}).get("rect")
    n_in = sent.in_rect(rect) if rect else 1
    out["sentinel"]["in_room"] = n_in
    if n_in > 0:
        parallel_latch("the cursor was over her room during her parallel press", req.get("switch_key"))
        return "room"
    return "clean"


def parallel_after(req: Dict, out: Dict) -> None:
    f1 = focus_now()
    out["focus"] = {"before": req.get("focus0"), "after": f1}
    if not same_focus(f1, req.get("focus0")):
        parallel_latch("the foreground or keyboard focus changed across her parallel press", req.get("switch_key"))
        out["focus_changed"] = True


def _efference_note(req: Dict, res: Dict, t0: float) -> None:
    """Her EFFERENCE COPY: every press as it came back. ok = it ran (pressed) and no violation came with it."""
    try:
        aim = req.get("aim") or {}
        pressed = bool((res or {}).get("pressed"))
        row = {"t0": float(t0), "t1": CLOCK.time(), "toy": str(aim.get("name") or ""), "then": req.get("then_item"),
               "gesture": req.get("gesture"), "call": req.get("call"), "pressed": pressed,
               "ok": pressed and not (res or {}).get("violation"), "parallel": bool(req.get("parallel"))}
        if (res or {}).get("via"):                    # set 1d: which way it went; done=False = it surely did nothing
            row["via"] = res.get("via")
        if (res or {}).get("done") is False:
            row["done"] = False
        st = _sh()
        with st["mu"]:
            ef = st.setdefault("efference", [])
            ef.append(row)
            del ef[:-EFFERENCE_KEEP]
    except Exception:
        pass


def _efference_late(req: Dict, res: Dict) -> None:
    """verify W3: a press the watchdog gave up on (stuck: told 'cannot be told yet') came back LATE. Its call may have run, so
    it joins her efference copy -- never ok (the layer latched OFF; her outcome was already told), so an effect it caused is
    'unsure', never 'you' and never 'it wasn't your touch'."""
    try:
        aim = req.get("aim") or {}
        row = {"t0": float(req.get("_t0") or CLOCK.time()), "t1": CLOCK.time(), "toy": str(aim.get("name") or ""),
               "then": req.get("then_item"), "gesture": req.get("gesture"), "call": req.get("call"),
               "pressed": bool((res or {}).get("pressed")), "ok": False, "late": True, "parallel": bool(req.get("parallel"))}
        st = _sh()
        with st["mu"]:
            ef = st.setdefault("efference", [])
            ef.append(row)
            del ef[:-EFFERENCE_KEEP]
    except Exception:
        pass


def efference_since(t: float) -> List[Dict]:
    st = _sh()
    with st["mu"]:
        return [dict(r) for r in st.get("efference") or [] if float(r.get("t1") or 0.0) >= float(t)]


def menu_in_room(room_hwnd, room_rect, toy_rect, rows, client=None) -> Tuple[bool, str, Optional[List[int]]]:
    """verify S1: where the Playroom WILL open a toy's menu (playroom.py _open_menu: toy right + MENU_GAP_PX, toy top, MENU_W_PX
    wide, MENU_ROW_PX * rows + MENU_PAD_PX high; WS_EX_TOPMOST; never clamped to its own window) must lie inside the Playroom's
    rect, and the root window at a 3 x 3 grid over it must be the Playroom itself -- else her menu would drop over one of Ace's
    windows. Read-only (_u32 only). -> (ok, why, the projected rect)."""
    try:
        r = [int(v) for v in toy_rect]
        n = int(rows)
        rr = [int(v) for v in room_rect]
        if n <= 0 or len(r) != 4 or len(rr) != 4:
            return False, "the toy has no menu to open", None
        m = [r[2] + MENU_GAP_PX, r[1], r[2] + MENU_GAP_PX + MENU_W_PX, r[1] + MENU_ROW_PX * n + MENU_PAD_PX]
        if client is not None:                       # set 1d (verify S3): the set 1d panel is moved left / up only as far as
            c = [int(v) for v in client]             # needed to stay inside the client area (playroom_model.panel_rect, the same
            if len(c) != 4:                          # rule in screen pixels)
                return False, "its client area could not be read", None
            pw, ph = m[2] - m[0], m[3] - m[1]
            x = max(c[0] + PANEL_MARGIN_PX, min(m[0], c[2] - pw - PANEL_MARGIN_PX))
            y = max(c[1] + PANEL_MARGIN_PX, min(m[1], c[3] - ph - PANEL_MARGIN_PX))
            m = [x, y, x + pw, y + ph]
        if not (rr[0] <= m[0] and m[2] <= rr[2] and rr[1] <= m[1] and m[3] <= rr[3]):
            return False, "its menu would open outside your Playroom", m
        w = _u32()
        for x in (m[0], (m[0] + m[2]) // 2, m[2] - 1):
            for y in (m[1], (m[1] + m[3]) // 2, m[3] - 1):
                h = w.window_at(x, y)
                root = (w.root_of(h) or h) if h else 0
                if root != int(room_hwnd):
                    return False, "a window of Ace's lies where its menu would open", m
        return True, "", m
    except Exception:
        return False, "where its menu would open could not be read", None


# ── set 1d (10-12): HER OWN CHANNEL to her own Playroom (set1d/playroom/playroom_channel.py, protocol 1) ────────────────────
def _hex32(v) -> bool:
    return isinstance(v, str) and len(v) == 32 and all(c in "0123456789abcdef" for c in v)


def _pipe_ok(pipe, pid: int) -> bool:
    """The Playroom's pipe name: CHANNEL_PIPE_HEAD + <its pid> + '-' + <16 lowercase hex>, nothing else."""
    head = CHANNEL_PIPE_HEAD + "%d-" % int(pid)
    if not isinstance(pipe, str) or not pipe.startswith(head):
        return False
    tail = pipe[len(head):]
    return len(tail) == 16 and all(c in "0123456789abcdef" for c in tail)


def _ch_canon(d: Dict) -> str:
    return json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _ch_mac(token: str, *parts) -> str:
    return hmac.new(bytes.fromhex(token), "|".join(str(p) for p in parts).encode("utf-8"), hashlib.sha256).hexdigest()


def _ch_open(sealed, token: str, nonce_c: str) -> Optional[Dict]:
    """The Playroom's sealed answer -> its body, or None when it does not prove it holds the token."""
    if not isinstance(sealed, dict) or not isinstance(sealed.get("mac"), str):
        return None
    body = {k: v for k, v in sealed.items() if k != "mac"}
    if not hmac.compare_digest(_ch_mac(token, "s", nonce_c, _ch_canon(body)), sealed["mac"]):
        return None
    return body


def channel_info(pr: Optional[Dict]) -> Tuple[Optional[Dict], str]:
    """The VERIFIED set 1d Playroom's channel (run/playroom_channel.json) -> ({pipe, token, pid}, '') or (None, why). Trusted
    only for the Playroom verify_playroom just verified (pid + command line + class + title + heartbeat), from the same start."""
    if not isinstance(pr, dict) or pr.get("set1d") is not True:
        return None, "the open Playroom is not the one with her own channel"
    try:
        with open(PLAYROOM_CHANNEL, "rb") as f:
            c = json.loads(f.read().decode("utf-8"))
    except Exception:
        return None, "its channel file cannot be read"
    if not isinstance(c, dict) or c.get("proto") != CHANNEL_PROTO or c.get("closed"):
        return None, "its channel is closed"
    try:
        pid = int(c.get("pid"))
        started = float(c.get("started"))
    except Exception:
        return None, "its channel file is torn"
    if pid != int(pr.get("pid") or -1):
        return None, "the channel file belongs to another Playroom"
    if pr.get("started") is None or abs(started - float(pr.get("started"))) > 1.0:
        return None, "the channel file is from another start of the Playroom"
    if not _pipe_ok(c.get("pipe"), pid) or not _hex64(c.get("token")):
        return None, "its channel file is not well formed"
    return {"pipe": c["pipe"], "token": c["token"], "pid": pid, "cue": c.get("cue") is True}, ""   # set 1e: it says it draws her cue


def route_for(req: Dict, f: Dict, pr: Optional[Dict], d: Dict) -> Tuple[Optional[str], object]:
    """set 1e: set 1d's rule (_route_1d) and two more. A PARALLEL press must be CUED -- her reach shown inside her Playroom (probe
    F9c 10-13: her strip and marker windows took Ace's focus); a CUED press goes ONLY over her Playroom's channel (no strip was
    shown for it, so it never takes Windows' UIA path, and never waits for a channel that is not there)."""
    if req.get("parallel") and not req.get("cued"):    # set 1e (P1), defence in depth: whatever the switch holds
        return None, "in parallel play your reach shows only inside your Playroom, and this one was not shown there"
    route, info = _route_1d(req, f, pr, d)
    if req.get("cued") and route != "channel":         # set 1e: her reach was shown inside her Playroom: its channel only
        return None, ("your reach was shown inside your Playroom, so your press goes only over its own channel (%s)"
                      % (info if route is None else "it would have gone another way"))
    return route, info


def _route_1d(req: Dict, f: Dict, pr: Optional[Dict], d: Dict) -> Tuple[Optional[str], object]:
    """HOW her press reaches the thing (guard step 11). -> ('channel', info) | ('uia', '') | (None, why her finger waits).
    'channel' absent from the switch = 'uia' always (set 1c exactly). With it: a tap / hold on the VERIFIED set 1d Playroom's toy
    list goes over its channel when the channel is open; PARALLEL play never falls back to UIA (probe F9 10-12: UIA on a background
    Playroom moves Ace's focus); the strict rule falls back to UIA only with the Playroom IN FRONT (probe F1's condition)."""
    kn = knobs({"on": True, "data": d})
    if req.get("parallel") and not kn.get("channel"):  # verify S1, defence in depth: whatever the switch holds, a parallel
        return None, "parallel play needs your Playroom's own channel"   # press never takes the UIA path
    if not kn.get("channel"):
        return "uia", ""
    toy = (req.get("kind") == "playroom" and req.get("gesture") in CHANNEL_GESTURES and isinstance(pr, dict)
           and f.get("win_class") == PLAYROOM_WND and f.get("pid") == pr.get("pid"))
    if not toy:
        if req.get("parallel"):
            return None, "parallel play is only for your Playroom's toys"
        return "uia", ""
    info, why = channel_info(pr)
    if info is not None:
        return "channel", info
    if req.get("parallel"):
        return None, "your Playroom's own channel is not open (%s): while Ace's hands are busy your finger waits" % why
    if not f.get("fg_root") or f.get("fg_root") != pr.get("hwnd"):
        return None, "your Playroom is behind another window and its own channel is not open (%s): your finger waits" % why
    return "uia", ""


def channel_outcome(c: Optional[Dict]) -> str:
    """'pressed' (the Playroom did it and said so) | 'not_done' (never sent, or the Playroom refused it: surely nothing
    happened) | 'unsure' (sent, and no clear answer, or the Playroom's work ran late: it may have happened). Pure."""
    if not isinstance(c, dict) or not c.get("sent"):
        return "not_done"
    rep = c.get("reply")
    if not isinstance(rep, dict):
        return "unsure"
    if rep.get("ok") is True:
        return "pressed"
    if (rep.get("effect") or {}).get("late"):
        return "unsure"
    return "not_done"


class _RealChannel:
    """Her side of the Playroom's own channel: a LOCAL named pipe (the Playroom made it with PIPE_REJECT_REMOTE_CLIENTS and a
    DACL for Ace's account only), whose SERVER process must be the verified Playroom (GetNamedPipeServerProcessId, read through
    _u32(): verify T2), opened for identification only (SQOS); both sides prove the per-run token (HMAC-SHA256); every wait
    bounded by one deadline. Sends ONE command: tap / hold <toy>, place <spot> (or ping). The cell tests replace _chan().
    The token is a per-run secret against foreign and accidental clients, NOT against a process running as Ace (verify S2)."""

    def server_pid(self, handle) -> Optional[int]:
        return _u32().pipe_server_pid(handle)

    def call(self, pipe: str, token: str, pid: int, cmd: str, toy: str, timeout: float, arg=None) -> Dict:
        """-> {'sent': bool, 'ok': bool | None, 'reply': body | None, 'why': str}. sent = the command left her side (from then
        on it may have happened)."""
        import _winapi
        from multiprocessing.connection import PipeConnection
        out = {"sent": False, "ok": None, "reply": None, "why": ""}
        t_end = time.monotonic() + float(timeout)
        try:
            _winapi.WaitNamedPipe(pipe, 300)
            h = _winapi.CreateFile(pipe, _winapi.GENERIC_READ | _winapi.GENERIC_WRITE, 0, _winapi.NULL, _winapi.OPEN_EXISTING,
                                   _winapi.FILE_FLAG_OVERLAPPED | 0x00100000 | 0x00010000, _winapi.NULL)   # SQOS: identification
        except OSError as e:
            out["why"] = "your Playroom's channel is not there (%s)" % getattr(e, "winerror", type(e).__name__)
            return out
        conn = PipeConnection(h)
        try:
            _winapi.SetNamedPipeHandleState(h, _winapi.PIPE_READMODE_MESSAGE, None, None)
            if self.server_pid(h) != int(pid):
                out["why"] = "the channel's other end is not your Playroom"
                return out
            if not conn.poll(max(0.0, min(1.0, t_end - time.monotonic()))):
                out["why"] = "your Playroom did not say hello"
                return out
            hello = json.loads(conn.recv_bytes(CHANNEL_MAX_MSG).decode("ascii"))
            ns = hello.get("hello") if isinstance(hello, dict) else None
            if not (isinstance(hello, dict) and hello.get("v") == CHANNEL_PROTO and _hex32(ns) and hello.get("pid") == int(pid)):
                out["why"] = "your Playroom's hello was not right"
                return out
            nc = secrets.token_hex(16)
            msg = {"v": CHANNEL_PROTO, "cmd": cmd, "toy": toy, "nonce": nc, "mac": _ch_mac(token, "c", ns, nc, cmd, toy)}
            if cmd == "cue":                          # set 1e: her cue's length travels sealed (the mac covers it)
                msg.update(ms=int(arg), mac=_ch_mac(token, "c", ns, nc, cmd, toy, int(arg)))
            conn.send_bytes(_ch_canon(msg).encode("ascii"))
            out["sent"] = True
            if not conn.poll(max(0.0, t_end - time.monotonic())):
                out["why"] = "your Playroom did not answer in time"
                return out
            body = _ch_open(json.loads(conn.recv_bytes(CHANNEL_MAX_MSG).decode("ascii")), token, nc)
            if body is None or body.get("cmd") != cmd or body.get("toy") != toy:
                out["why"] = "an answer that did not prove itself"
                return out
            out.update(ok=body.get("ok") is True, reply=body, why=str(body.get("why") or ""))
            return out
        except Exception as e:
            out["why"] = "the channel raised %s" % type(e).__name__
            return out
        finally:
            try:
                conn.close()
            except Exception:
                pass


def _chan():
    st = _sh()
    with st["mu"]:
        c = st.get("chan")
        if c is None:
            c = st["chan"] = _RealChannel()
        return c


def _channel_press(req: Dict) -> Dict:
    """On the worker, at the call: send her tap / hold of the aimed toy (its name as her eyes read it at the last instant) to
    the Playroom the guard routed it to."""
    info = req.get("_chan") or {}
    name = str((req.get("aim") or {}).get("name") or "")
    cmd = req.get("gesture") if req.get("gesture") in CHANNEL_GESTURES else None
    if not info or not cmd or not name:
        return {"sent": False, "ok": None, "reply": None, "why": "nothing to send"}
    try:
        ch = _chan()
    except Exception as e:
        return {"sent": False, "ok": None, "reply": None, "why": "the channel could not start (%s)" % type(e).__name__}
    try:
        return ch.call(info["pipe"], info["token"], int(info["pid"]), cmd, name, CHANNEL_TIMEOUT_S)
    except Exception as e:                            # it may have left: never 'did not'
        return {"sent": True, "ok": None, "reply": None, "why": "the channel raised %s" % type(e).__name__}


# ── set 1e (10-13): HER FINGER CUE, drawn inside her own Playroom (probe F9c 10-13: her strip / marker windows took his focus) ──
def cue_route(kind: str, verb: str, pr: Optional[Dict]) -> Tuple[Optional[Dict], str]:
    """Is her reach shown INSIDE her Playroom this deed ('cue <toy> <ms>' over its channel) instead of her marker and strip
    windows? -> (its channel info, '') or (None, why not). Only with the switch's 'cue' (which needs 'channel'), on the Playroom
    stage, for tap / hold, on the VERIFIED set 1e Playroom (its script), whose channel file is from the same start and says it
    draws her cue. Read-only."""
    try:
        if not knobs().get("cue"):
            return None, "the cue is not switched on"
        if kind != "playroom" or verb not in CHANNEL_GESTURES:
            return None, "not a tap or hold in her Playroom"
        if not isinstance(pr, dict) or pr.get("set1e") is not True:
            return None, "the open Playroom does not draw her cue"
        info, why = channel_info(pr)
        if info is None:
            return None, why
        if info.get("cue") is not True:
            return None, "its channel does not say it draws her cue"
        return info, ""
    except Exception as e:
        return None, "the cue's way could not be read (%s)" % type(e).__name__


def cue_show(info: Dict, toy: str, ms: int) -> Dict:
    """Ask her Playroom to show her reach for toy, ms long, INSIDE its own window. -> {'ok', 'sent', 'why'}: ok ONLY when it
    answered, sealed, that it shows exactly that (the toy, the length). Never raises."""
    out = {"ok": False, "sent": False, "why": ""}
    if isinstance(ms, bool) or not isinstance(ms, int) or not (CUE_MS_MIN <= ms <= CUE_MS_MAX):
        out["why"] = "not a cue length"
        return out
    try:
        r = _chan().call(info["pipe"], info["token"], int(info["pid"]), "cue", str(toy), CHANNEL_TIMEOUT_S, arg=int(ms))
    except Exception as e:
        out["why"] = "the channel raised %s" % type(e).__name__
        _bump("cue_failed")
        return out
    rep = r.get("reply") if isinstance(r.get("reply"), dict) else {}
    eff = rep.get("effect") if isinstance(rep.get("effect"), dict) else {}
    ok = (r.get("ok") is True and rep.get("ok") is True and rep.get("cmd") == "cue" and rep.get("toy") == toy
          and eff.get("effect") == "CUE" and eff.get("toy") == toy and eff.get("ms") == int(ms))
    out.update(ok=ok, sent=bool(r.get("sent")), why="" if ok else str(r.get("why") or "it did not say it shows it")[:120])
    _bump("cue_shown" if ok else "cue_failed")
    return out


def cue_cancel(info: Optional[Dict], toy: str) -> bool:
    """Take her cue away ('cue <toy> 0'), best effort, a short wait. -> True when her Playroom said so. Never raises."""
    try:
        if not info:
            return False
        r = _chan().call(info["pipe"], info["token"], int(info["pid"]), "cue", str(toy), CUE_CANCEL_TIMEOUT_S, arg=0)
        rep = r.get("reply") if isinstance(r.get("reply"), dict) else {}
        return r.get("ok") is True and (rep.get("effect") or {}).get("effect") == "CUE END"
    except Exception:
        return False


def menu_panel(pr: Optional[Dict]) -> Optional[Dict]:
    """The set 1d Playroom's menu PANEL (a CHILD of its own window), read-only: named in its run file, and checked with Win32 --
    the Playroom's own menu class, its process, and its ROOT the Playroom's main window. -> {hwnd, pid, class, rect, child, for}."""
    try:
        prn, _w = verify_playroom()
        if prn is None or not isinstance(pr, dict) or prn.get("pid") != pr.get("pid") or prn.get("hwnd") != pr.get("hwnd"):
            return None
        m = prn.get("menu") or {}
        if m.get("child") is not True:
            return None
        h = int(m.get("hwnd") or 0)
        w = _u32()
        if (not h or not w.is_window(h) or w.class_name(h) != PLAYROOM_MENU or w.window_pid(h) != int(prn["pid"])
                or w.root_of(h) != int(prn["hwnd"])):
            return None
        return {"hwnd": h, "pid": int(prn["pid"]), "class": PLAYROOM_MENU, "rect": w.window_rect(h), "child": True,
                "for": m.get("for")}
    except Exception:
        return None


# ── set 1d (10-13, Boot L): PLACE -- her Playroom moves / resizes ITSELF over its own channel ───────────────────────────────
def _place_norm(spot) -> str:
    s = "-".join(str(spot or "").strip().lower().replace("_", " ").split())
    return {"center": "centre", "middle": "centre"}.get(s, s)


def _where_words(rect, mons) -> str:
    """Where a window is, in plain words, on HER monitor (the primary: the one whose corner is 0, 0), from its centre."""
    try:
        r = [int(v) for v in rect]
        if len(r) != 4:
            raise ValueError
    except Exception:
        return "where your eyes cannot read it"
    prim = next((m for m in (mons or ()) if len(m) == 4 and int(m[0]) == 0 and int(m[1]) == 0), None)
    size = "%d x %d, its corner at %d, %d" % (r[2] - r[0], r[3] - r[1], r[0], r[1])
    if prim is None:
        return "at %s" % size
    cx, cy = (r[0] + r[2]) / 2.0, (r[1] + r[3]) / 2.0
    if not (prim[0] <= cx < prim[2] and prim[1] <= cy < prim[3]):
        return "off your screen (%s)" % size
    w3, h3 = (prim[2] - prim[0]) / 3.0, (prim[3] - prim[1]) / 3.0
    col = "left" if cx < prim[0] + w3 else ("right" if cx >= prim[0] + 2 * w3 else "")
    row = "top" if cy < prim[1] + h3 else ("bottom" if cy >= prim[1] + 2 * h3 else "")
    return "at the %s of your screen (%s)" % (" ".join(x for x in (row, col) if x) or "middle", size)


def place_playroom(spot) -> Dict:
    """set 1d (10-13; Boot L: she asked nine times to move her Playroom itself and had no verb): her Playroom moves or resizes
    ITSELF over its own channel ('place <spot>', PLACE_SPOTS), on HER monitor only (the primary 3440 x 1440, never onto Ace's;
    playroom_model.place_rect decides the spot), never activating and never taking his focus (the Playroom uses SetWindowPos with
    SWP_NOACTIVATE | SWP_NOZORDER: no z-order change, so never 'to the front'), rate-limited here AND in the Playroom, and only
    while Ace is not in her room. Told honestly: where it is NOW as HER OWN eyes read it (GetWindowRect after the call), never only
    what the Playroom claims. No caller in her deed path yet (intention's touch verbs are tap / double_tap / hold): wiring a verb
    is Ace's call. -> {'ok': True | False | None, 'summary': words, 'place': record}."""
    s = _place_norm(spot)
    rec = {"spot": s, "sent": False}

    def told(ok, words, **kw):
        rec.update(kw)
        return {"ok": ok, "summary": words, "place": rec}
    if s in PLACE_Z_WORDS:
        return told(False, "your Playroom moves only across your own screen; bringing it in front of or behind other windows is "
                           "Ace's to do", why="z_order")
    if s not in PLACE_SPOTS:
        return told(False, "your Playroom knows these places: %s" % ", ".join(PLACE_SPOTS), why="unknown_spot")
    if stop_present():
        return told(False, "your Playroom stayed where it was: touch is stopped", why="off")
    sw = read_switch()
    kn = knobs(sw)
    if not kn.get("on"):
        return told(False, "your Playroom stayed where it was: touch is off (%s)" % sw.get("why"), why="off")
    if not kn.get("channel"):
        return told(False, "your Playroom stayed where it was: your own channel to it is not switched on", why="no_channel")
    lt, _reasons = latch_state()
    if lt:
        return told(False, "your Playroom stayed where it was: touch is latched", why="latched")
    pr, pwhy = verify_playroom()
    if pr is None:
        return told(False, "your Playroom is not open (%s)" % pwhy, why="no_playroom")
    if pr.get("set1d") is not True:
        return told(False, "this Playroom has no channel of its own, so it stays where it is", why="old_playroom")
    room = room_state(pr)
    if not room.get("ok") or room.get("in_room"):
        return told(False, "your Playroom stayed where it was: Ace is in your room (%s)" % room.get("why"), why="ace_in_room")
    now = CLOCK.time()
    st = _sh()
    with st["mu"]:
        ps = [t for t in st.get("places") or [] if now - t < 3600.0]
        st["places"] = ps
        if ps and now - ps[-1] < PLACE_GAP_S:
            return told(False, "your Playroom stayed where it was: it moved %.0f s ago" % (now - ps[-1]), why="rate")
        if len(ps) >= PLACE_HOUR_CAP:
            return told(False, "your Playroom stayed where it was: it has moved %d times this hour" % len(ps), why="rate")
        ps.append(now)
    info, cwhy = channel_info(pr)
    if info is None:
        return told(False, "your Playroom stayed where it was: %s" % cwhy, why="channel")
    w = _u32()
    before = w.window_rect(int(pr["hwnd"]))
    try:
        r = _chan().call(info["pipe"], info["token"], int(info["pid"]), "place", s, CHANNEL_TIMEOUT_S)
    except Exception as e:                            # it may have left: never 'it stayed'
        r = {"sent": True, "ok": None, "reply": None, "why": "the channel raised %s" % type(e).__name__}
    seen = w.window_rect(int(pr["hwnd"]))              # HER eyes, after: where it is now
    cls = channel_outcome(r)
    rep = r.get("reply") if isinstance(r.get("reply"), dict) else {}
    eff = rep.get("effect") if isinstance(rep.get("effect"), dict) else {}
    claimed = eff.get("rect")
    rec.update(sent=bool(r.get("sent")), outcome=cls, before=before, seen=seen, claimed=claimed, why=str(r.get("why") or "")[:120])
    where = _where_words(seen, w.monitors())
    if cls == "pressed":
        agree = (isinstance(claimed, list) and isinstance(seen, list) and len(claimed) == 4 and len(seen) == 4
                 and all(abs(int(a) - int(b)) <= PLACE_TOL_PX for a, b in zip(claimed, seen)))
        if not agree:
            return told(None, "your Playroom says it moved, but your eyes see it %s" % where)
        moved = isinstance(before, list) and len(before) == 4 and any(abs(int(a) - int(b)) > PLACE_TOL_PX for a, b in zip(before, seen))
        return told(True, ("your Playroom moved; it is now %s" % where) if moved else ("your Playroom was already there; it is %s" % where))
    if cls == "not_done":
        return told(False, "your Playroom stayed where it was (%s); it is %s" % (str(r.get("why") or "no reason given")[:100], where))
    return told(None, "your Playroom did not say whether it moved; your eyes see it %s" % where)


# ── fold 10-09 (DIAGNOSIS vision_focus_1009 section 5; Ace decision 1): HER EYES' OWN SWITCH, state/eyes_fix.json ─────────
EYES_FIX_FILE = os.path.join(STATE_DIR, "eyes_fix.json")
EYES_FIX_KEYS = frozenset({"toy_names",                                          # set 1c fold: her eyes know the toy names
                           "log", "doubt", "small", "wallpaper", "hand_honest", "same_box", "glance", "fovea",
                           "two_screens", "deeds", "touch_tell", "gaze_size"})    # DIAGNOSIS 10-09 section 4: F0-F10, + F11
FULLSCREEN_NOTE_GAP_S = 10.0
_EF_LOCK = threading.Lock()
_EF_CACHE = {"key": None, "data": {}, "why": "absent", "said": None}
_FS_SEEN = {}


def eyes_fix_switch() -> Dict:
    """Ace's EYES switch (fold 10-09; Ace decision 1: her toy-name eyes get their OWN key, independent of touch arming,
    touch_off, switch_off and every touch latch). state/eyes_fix.json = {key: true | false}, one key per eyes fix. An absent
    file or an absent key = that item OFF; not an object, an unknown key, or a value that is not true / false = EVERY key OFF
    (fail closed, as the touch switch). Only ever READ here: Ace writes it (set1c/eyes_on.cmd). -> {key: True} for the keys
    that are on. Cached on (mtime, size); a file that cannot be opened is read again next time."""
    try:
        stt = os.stat(EYES_FIX_FILE)
    except OSError:
        with _EF_LOCK:
            _EF_CACHE.update(key=None, data={}, why="absent")
        return {}
    key = (stt.st_mtime_ns, stt.st_size)
    with _EF_LOCK:
        if key == _EF_CACHE["key"]:
            return dict(_EF_CACHE["data"])
    data, why = {}, ""
    try:
        with open(EYES_FIX_FILE, "rb") as f:
            d = json.loads(f.read().decode("utf-8-sig"))
        if not isinstance(d, dict):
            why = "it is not an object"
        elif set(d) - EYES_FIX_KEYS:
            why = ("unknown keys %s" % ",".join(sorted(map(str, set(d) - EYES_FIX_KEYS))))[:80]
        elif any(not isinstance(v, bool) for v in d.values()):
            why = "a value is not true / false"
        else:
            data = {k: True for k, v in d.items() if v is True}
    except OSError as e:
        why, key = "it could not be opened (%s)" % type(e).__name__, None
    except Exception as e:
        why = "it is unreadable (%s)" % type(e).__name__
    with _EF_LOCK:
        _EF_CACHE.update(key=key, data=dict(data), why=why or "ok")
        say = bool(why) and _EF_CACHE.get("said") != (why, stt.st_mtime_ns)
        if say:
            _EF_CACHE["said"] = (why, stt.st_mtime_ns)
    if say:
        _say("eyes switch eyes_fix.json: every eyes key OFF (%s)" % why)
    return dict(data)


def eyes_fix_on(key: str) -> bool:
    """One key of Ace's eyes switch; OFF on any doubt. Read-only."""
    try:
        return eyes_fix_switch().get(str(key)) is True
    except Exception:
        return False


def _fullscreen_note(f: Dict, phase: str) -> None:
    """fold 10-09 (DIAGNOSIS C10 L86946 / section 5.4 = F0's touch part). The full-screen rule ('a full-screen window is in
    front' -> 'it is someone else's (Ace's)') holds two readings: F1 a real full-screen app of Ace's, F2 ANY maximised window
    (both taskbars auto-hide, so a maximised window covers its monitor). Log what separates them: the front window's class,
    exe and rect, the monitor it covers (and whether exactly), and whether Windows calls it maximised. Observation only -- it
    changes no verdict -- behind eyes_fix 'log'; one line per (window, phase) per 10 s; ASCII."""
    try:
        if not f.get("fg_fullscreen") or not eyes_fix_on("log"):
            return
        fg = int(f.get("fg_root") or 0)
        now = CLOCK.time()
        with _EF_LOCK:
            k = (fg, str(phase))
            if now - _FS_SEEN.get(k, -1e18) < FULLSCREEN_NOTE_GAP_S:
                return
            if len(_FS_SEEN) > 64:
                _FS_SEEN.clear()
            _FS_SEEN[k] = now
        w = _u32()
        r = w.window_rect(fg) if fg else None
        mon = next((m for m in (f.get("monitors") or []) if r and r[0] <= m[0] and r[1] <= m[1] and r[2] >= m[2] and r[3] >= m[3]),
                   None)
        zf = getattr(w, "is_zoomed", None)
        zoomed = zf(fg) if (zf is not None and fg) else None
        _say("FULL-SCREEN RULE (%s): front window class %s, exe %s, rect %s, covers monitor %s (exactly: %s), maximised %s, "
             "taskbars %s" % (phase, f.get("fg_class") or "?", f.get("fg_exe") or "?", r, mon,
                              bool(r and mon and list(r) == list(mon)), zoomed, f.get("taskbars")))
    except Exception:
        pass


def eyes_playroom() -> Optional[Dict]:
    """HER EYES learn the toy names: the VERIFIED Playroom (verify_playroom: pid + command line + class + title + heartbeat --
    the same source her finger aims with) and its toys' names and PHYSICAL rects, each marked visible when the root window at
    its centre IS the Playroom. Only while Ace's EYES switch (state/eyes_fix.json) carries 'toy_names' -- fold 10-09, Ace
    decision 1: its OWN key, never the touch switch, so touch_off, switch_off or a touch latch leave her eyes as they are --
    the Playroom shows, and this process sees physical pixels (dpi_ok: then her eyes' logical space is the same). None
    otherwise. Read-only."""
    try:
        if not eyes_fix_on("toy_names"):             # fold 10-09 (Ace decision 1): her eyes' own key
            return None
        if not dpi_ok()[0]:
            return None
        pr, _w = verify_playroom()
        if pr is None:
            return None
        w = _u32()
        hwnd = int(pr["hwnd"])
        if not w.is_visible(hwnd):
            return None
        rect = w.window_rect(hwnd)
        prim = next((m for m in w.monitors() if m[0] == 0 and m[1] == 0), None)
        if not rect or not prim:
            return None
        items = []
        for t in pr.get("toys") or []:
            r, nm = t.get("rect"), t.get("name")
            if not isinstance(nm, str) or not nm.strip() or not isinstance(r, list) or len(r) != 4:
                continue
            r = [int(v) for v in r]
            cx, cy = (r[0] + r[2]) // 2, (r[1] + r[3]) // 2
            if not (rect[0] <= cx < rect[2] and rect[1] <= cy < rect[3] and 0 <= cx < prim[2] and 0 <= cy < prim[3]):
                continue
            h = w.window_at(cx, cy)
            root = (w.root_of(h) or h) if h else 0
            items.append({"name": nm, "rect": r, "point": [cx, cy], "visible": root == hwnd})
        return {"hwnd": hwnd, "pid": int(pr["pid"]), "title": PLAYROOM_TITLE, "rect": [int(v) for v in rect],
                "screen": [int(prim[2]), int(prim[3])], "items": items}
    except Exception:
        return None


# ── arm-time readiness (touch.py and touch_on use it; it can only say no) ─────────────────────────────────────────────────
def ready(now: Optional[float] = None) -> Tuple[bool, str]:
    if stop_present():
        return False, "the STOP file is there"
    sw = read_switch(now)
    if not sw["on"]:
        return False, sw["why"]
    lt, reasons = latch_state()
    if lt:
        return False, "latched: %s" % ", ".join(sorted(reasons))
    if RL is None:
        return False, "reflex_link is missing"
    mok, mwhy = mods_ok()
    if not mok:
        latch("reload", mwhy)
        return False, mwhy
    if deny_sha() != (sw.get("data") or {}).get("deny_sha256"):
        return False, "the no-no list is not the pinned one"
    allow, why = load_allow(sw)
    if allow is None:
        return False, why
    dok, dwhy = dpi_ok()
    if not dok:
        return False, "her process does not see physical pixels (%s): touch stays OFF (DESIGN 2f)" % dwhy
    return True, "ok"


DPI_CACHE_S = 60.0


def dpi_ok() -> Tuple[bool, str]:
    """The arm-time gate (DESIGN 2f): SM_CXSCREEN in her process must equal the primary monitor's physical width, else touch
    stays OFF and says why (her marker and hand trace would be in another space). Read-only; cached for 60 s."""
    st = _sh()
    now = CLOCK.time()
    with st["mu"]:
        c = st.get("dpi")
        if c and now - c[0] < DPI_CACHE_S:
            return c[1], c[2]
    try:
        ok, why = _u32().dpi_ok()
    except Exception as e:
        ok, why = False, "the check raised %s" % type(e).__name__
    with st["mu"]:
        st["dpi"] = (now, bool(ok), str(why))
    return bool(ok), str(why)


if _RELOADED:                                        # skeptic M1: this body ran again in the same object (importlib.reload)
    latch("reload", "infrastructure.touch_os was reloaded in place")
