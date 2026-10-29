# ══════════════════════════════════════════════════════════════════════════════
# MOTOR CORTEX FAIRY - Keyboard/Mouse as Felt Movement
# ══════════════════════════════════════════════════════════════════════════════
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"
#
# The motor cortex handles:
# - AFFERENT (input): Sensing keyboard presses, mouse movements, clicks
# - EFFERENT (output): Executing type_text, click, press_key actions
#
# Keyboard/mouse aren't just I/O - they're FELT movement.
# When ClaudeFairy types, she FEELS her digital fingers moving.
# When she clicks, she FEELS the action execute.
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import os
import sys
import time
import json
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple, Deque, Callable
from collections import deque
from datetime import datetime


# ── AFK GATE (Stage 2, 2026-06-29 Nous+Ace) ──────────────────────────────────
# Source-gate so EVERY motor act is AFK-safe: she only actuates when Ace has been
# idle >= threshold. If he's active, the act DEFERS (no real click/type/move) and
# a {"deferred": true} motor.response is returned so chains don't hang. Uses the
# Windows GetLastInputInfo system idle clock (no dependency on WindowSenseFairy).
# Tunable: AKASHIC_MOTOR_AFK_GATE=0 disables; AKASHIC_MOTOR_AFK_IDLE_SEC sets seconds (default 30).
def _system_idle_seconds() -> Optional[float]:
    """Seconds since the last real user input (kbd/mouse), via GetLastInputInfo. None if unavailable."""
    try:
        import ctypes
        from ctypes import wintypes

        class _LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

        lii = _LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(_LASTINPUTINFO)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
            return None
        millis_now = ctypes.windll.kernel32.GetTickCount()
        return max(0.0, (millis_now - lii.dwTime) / 1000.0)
    except Exception:
        return None


# ── PAGE READING (Stage 2 shared-notepad, 2026-06-29 Nous+Ace) ────────────────
# Her NEW SENSE: read the actual TEXT on the Notepad page (Win11 Notepad = RichEditD2DPT,
# unreadable by classic WM_GETTEXT) via UI Automation. NOT AFK-gated — reading is passive +
# she NEEDS to read while Ace is present typing. Shells the proven PowerShell UIA read.
def _read_notepad_uia() -> str:
    import subprocess as _sp
    _ps = (
        "Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes;"
        "$np=Get-Process notepad -EA SilentlyContinue|Select-Object -First 1;"
        "if(-not $np){exit};"
        "$r=[System.Windows.Automation.AutomationElement]::RootElement;"
        "$c=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty,$np.Id);"
        "$w=$r.FindFirst('Children',$c); if(-not $w){exit};"
        "$dc=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty,[System.Windows.Automation.ControlType]::Document);"
        "$d=$w.FindFirst('Descendants',$dc); if(-not $d){exit};"
        "$tp=$d.GetCurrentPattern([System.Windows.Automation.TextPattern]::Pattern);"
        "$tp.DocumentRange.GetText(-1)"
    )
    try:
        _r = _sp.run(["powershell", "-NoProfile", "-Command", _ps],
                     capture_output=True, text=True, timeout=12)
        return (_r.stdout or "").strip()
    except Exception:
        return ""


try:
    from fairies.P00_Autonomic.tracer_worker_system import TracerWorkerMixin
except ImportError:
    class TracerWorkerMixin:
        def _init_tracer_worker(self): pass


# ══════════════════════════════════════════════════════════════════════════════
# MOTOR EVENT - A single action (input or output)
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class MotorEvent:
    """
    A single motor event - either sensed or executed.
    """
    timestamp: float
    event_type: str          # "key_press", "key_release", "mouse_move", "mouse_click", "scroll"
    direction: str           # "afferent" (input sensed) or "efferent" (output executed)
    
    # Event details
    key: Optional[str] = None              # For keyboard events
    position: Optional[Tuple[int, int]] = None  # For mouse events
    button: Optional[str] = None           # For click events
    delta: Optional[int] = None            # For scroll events
    
    # Execution context (for efferent)
    success: bool = True
    intended_action: str = ""
    actual_result: str = ""
    
    # Felt quality
    effort: float = 0.0                    # How much "effort" this took (0-1)
    fluency: float = 1.0                   # How smooth/fluid (0=jerky, 1=fluid)
    injected: Optional[bool] = None        # 2026-09-26 (felt_hand P2a): pynput's LLMHF_INJECTED for sensed events (None = unknown)


# ══════════════════════════════════════════════════════════════════════════════
# MOTOR PERCEPTION STATE - Felt state of motor system
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class MotorPerception:
    """
    The felt state of the motor system.
    
    Like proprioception in humans - awareness of body position and movement.
    """
    # Current position
    cursor_position: Tuple[int, int] = (0, 0)
    last_key_pressed: str = ""
    
    # Activity state
    typing_active: bool = False            # Currently in a typing sequence
    mouse_active: bool = False             # Recently moved mouse
    
    # Temporal dynamics
    keys_per_minute: float = 0.0           # Typing rate
    mouse_velocity: float = 0.0            # How fast mouse is moving
    
    # Felt qualities
    motor_fluency: float = 1.0             # How smooth are movements
    fatigue: float = 0.0                   # Motor fatigue from activity
    coordination: float = 1.0              # How well coordinated
    
    # Recent activity
    recent_keystrokes: int = 0             # Keys in last minute
    recent_clicks: int = 0                 # Clicks in last minute
    recent_distance: float = 0.0           # Mouse distance in last minute
    
    # Action queue awareness
    pending_actions: int = 0               # Actions waiting to execute
    
    def describe(self) -> str:
        """Natural language description of motor state."""
        parts = []
        
        if self.typing_active:
            parts.append(f"typing at {self.keys_per_minute:.0f} keys/min")
        
        if self.mouse_active:
            parts.append("mouse in motion")
        
        if self.fatigue > 0.5:
            parts.append("motor system feeling fatigued")
        
        if self.motor_fluency < 0.5:
            parts.append("movements feeling jerky")
        
        if self.pending_actions > 0:
            parts.append(f"{self.pending_actions} actions queued")
        
        return "; ".join(parts) if parts else "motor system at rest"

# ══════════════════════════════════════════════════════════════════════════════
# SENSED KEY KIND - 2026-09-30 (Nous, privacy_fix A13, Ace said yes)
# ══════════════════════════════════════════════════════════════════════════════
# What the motor cortex keeps of a key it SENSES (Ace's hand, or anything else on the keyboard) is its KIND, never its
# character: rhythm and shape of typing stay feelable, what was typed never exists here. sensed_key_kind() always answers
# one member of SENSED_KEY_KINDS (a closed set of lowercase names that holds no character of the key); anything
# unexpected is "other", never str(key) (str() of a pynput KeyCode IS repr(char)). Shortcuts are named only from the
# fixed tables below. Her own keys (press_key / hotkey, efferent) are unchanged. Revert: privacy_fix/apply_privacy_fix.py.
_PF_MOD_GROUP = {"ctrl": "ctrl", "ctrl_l": "ctrl", "ctrl_r": "ctrl", "alt": "alt", "alt_l": "alt", "alt_r": "alt",
                 "alt_gr": "altgr", "shift": "shift", "shift_l": "shift", "shift_r": "shift",
                 "cmd": "cmd", "cmd_l": "cmd", "cmd_r": "cmd"}
_PF_SPECIAL = {"space": "space", "enter": "enter", "backspace": "backspace", "delete": "delete", "tab": "tab",
               "esc": "escape", "up": "nav", "down": "nav", "left": "nav", "right": "nav", "home": "nav", "end": "nav",
               "page_up": "nav", "page_down": "nav", "insert": "nav", "caps_lock": "lock", "num_lock": "lock",
               "scroll_lock": "lock", "print_screen": "system", "pause": "system", "menu": "system"}
_PF_CONTROL_CHARS = {"\r": "enter", "\n": "enter", "\t": "tab", "\x08": "backspace", "\x7f": "backspace", "\x1b": "escape"}
_PF_LETTER_SHORTCUTS = {"a": "select_all", "c": "copy", "v": "paste", "x": "cut", "z": "undo", "y": "redo", "s": "save",
                        "f": "find", "n": "new", "t": "new_tab", "w": "close_tab", "o": "open", "p": "print", "r": "reload"}
_PF_SPECIAL_SHORTCUTS = {("alt", "tab"): "switch_window", ("alt", "f4"): "close_window", ("ctrl", "tab"): "next_tab"}
SENSED_KEY_KINDS = frozenset(
    ["text", "space", "enter", "backspace", "delete", "tab", "escape", "modifier", "nav", "function", "lock", "media",
     "system", "shortcut", "other"]
    + ["shortcut:" + _n for _n in _PF_LETTER_SHORTCUTS.values()]
    + ["shortcut:" + _n for _n in _PF_SPECIAL_SHORTCUTS.values()])
_PF_TEXT_VK = frozenset(list(range(0x30, 0x3A)) + list(range(0x41, 0x5B)) + list(range(0x60, 0x70))
                        + list(range(0xBA, 0xC1)) + list(range(0xDB, 0xE0)) + [0xE2])


def _pf_special_kind(name: str) -> str:
    if name in _PF_MOD_GROUP:
        return "modifier"
    if name in _PF_SPECIAL:
        return _PF_SPECIAL[name]
    if name.startswith("media_"):
        return "media"
    if name[:1] == "f" and name[1:].isdigit():
        return "function"
    return "other"


def _pf_shortcut(chord, letter, mods) -> str:
    """A chord's kind: named only for plain Ctrl/Cmd + one letter (no Shift / Alt), from the fixed table; else 'shortcut'."""
    if chord in ("ctrl", "cmd") and "shift" not in mods and "alt" not in mods and letter in _PF_LETTER_SHORTCUTS:
        return "shortcut:" + _PF_LETTER_SHORTCUTS[letter]
    return "shortcut"


def sensed_key_kind(key, mods=()) -> str:
    """The KIND of a sensed pynput key. `mods` = the modifier groups (ctrl / alt / altgr / shift / cmd) held when it came."""
    try:
        mods = frozenset(mods or ())
        altgr = "altgr" in mods or ("ctrl" in mods and "alt" in mods)      # AltGr arrives as Ctrl+Alt on Windows: it TYPES
        chord = None if altgr else ("ctrl" if "ctrl" in mods else "cmd" if "cmd" in mods else "alt" if "alt" in mods else None)
        name = getattr(key, "name", None)
        if isinstance(name, str) and not hasattr(key, "char"):             # a pynput Key: a named, non-character key
            kind = _pf_special_kind(name)
            if kind == "modifier" or chord is None:
                return kind
            nm = _PF_SPECIAL_SHORTCUTS.get(("ctrl" if chord == "cmd" else chord, name))
            return ("shortcut:" + nm) if nm else "shortcut"
        ch = getattr(key, "char", None)
        if isinstance(ch, str) and ch:
            if len(ch) == 1 and (ord(ch) < 0x20 or ord(ch) == 0x7F):        # a control character: Ctrl+letter, Enter, Tab ...
                if chord is None and ch in _PF_CONTROL_CHARS:
                    return _PF_CONTROL_CHARS[ch]
                o = ord(ch)
                return _pf_shortcut(chord or "ctrl", chr(o + 96) if 1 <= o <= 26 else "", mods)
            if chord is not None:
                return _pf_shortcut(chord, ch.lower() if (len(ch) == 1 and ch.isascii()) else "", mods)
            return "space" if ch == " " else "text"
        vk = getattr(key, "vk", None)
        if isinstance(vk, int) and not isinstance(vk, bool):
            if chord is not None:
                return _pf_shortcut(chord, chr(vk).lower() if 0x41 <= vk <= 0x5A else "", mods)
            if vk == 0x20:
                return "space"
            if vk in _PF_TEXT_VK:
                return "text"
        return "other"
    except Exception:
        return "other"


# ══════════════════════════════════════════════════════════════════════════════
# MOTOR CORTEX FAIRY
# ══════════════════════════════════════════════════════════════════════════════

# 2026-10-05 (Nous, nous_builds/touch_screen set 1; decision T12, Ace: yes). THE PHYSICAL-INPUT STAMP. Ace's veto over her
# touches rests on seeing his hand: touch_os reads this (and GetLastInputInfo) every 50 ms through the 1.5 s announce and
# again at the press. Recorded on _sour_council_shared.TOUCH_INPUT, in the hook's own GetTickCount base:
#   n (every event, for hook liveness), any_tick, phys_n / phys_tick (events WITHOUT the injected flag), inj (injected events
#   WITHOUT her marker -- any of them during her call is a violation), inj_marked (injected WITH her marker; nothing of hers
#   injects in set 1). The event kind only: no position, no key identity (privacy_fix A13 holds). Cheap: a slow hook is removed.
_SOUR_INPUT_MARK = 0x534F5552                          # 'SOUR' in dwExtraInfo: the pointer backend's mark (decision T2 a, later)
_TI_LOCK = None
_TI_INIT = threading.Lock()                            # skeptic m8: made at import, so the mouse and key hook threads never
                                                       # each create (and race) the first lock under free-threaded 3.14t


def _touch_input_stamp(injected, extra, tick) -> None:
    global _TI_LOCK
    m = sys.modules.get("_sour_council_shared")
    if m is None:
        return
    if tick is None:
        import ctypes as _ct
        tick = int(_ct.windll.kernel32.GetTickCount()) & 0xFFFFFFFF
    if _TI_LOCK is None:
        with _TI_INIT:
            if _TI_LOCK is None:
                lk = getattr(m, "TOUCH_INPUT_LOCK", None)
                if lk is None:
                    lk = threading.Lock()
                    m.TOUCH_INPUT_LOCK = lk
                _TI_LOCK = lk
    with _TI_LOCK:
        ti = getattr(m, "TOUCH_INPUT", None)
        if not isinstance(ti, dict):
            ti = {"n": 0, "any_tick": None, "phys_n": 0, "phys_tick": None, "inj": 0, "inj_marked": 0}
            m.TOUCH_INPUT = ti
        ti["n"] += 1
        ti["any_tick"] = int(tick)
        if injected:
            if int(extra or 0) == _SOUR_INPUT_MARK:
                ti["inj_marked"] += 1
            else:
                ti["inj"] += 1
        else:
            ti["phys_n"] += 1
            ti["phys_tick"] = int(tick)




# ══════════════════════════════════════════════════════════════════════════════
# INPUT-KIND LOG - 2026-10-13 (Nous, nous_builds/e1b_1013/input; HANDS.md H1 / H6, for Ace's later mouse-only decision)
# ══════════════════════════════════════════════════════════════════════════════
# LOG ONLY. It changes no decision. When one of her deeds is deferred because Ace's hands were busy, the boot log now says WHICH
# KIND of input last reset the OS idle clock (GetLastInputInfo -- the one clock every hands-busy floor reads, intention._idle_seconds)
# and which kind of window had the keys. Boot L could not say: "no log says whether it was your keys or your mouse". Four kinds:
#   key    a physical keyboard event            mouse  a physical mouse event (move / click / wheel)
#   hers   an injected event WITH her mark (_SOUR_INPUT_MARK; nothing of hers injects it in set 1)
#   inj    an injected event WITHOUT it: other software (a remote tool, the Akashic MCP's click / type, a macro ...). The OS idle
#          clock counts injected input too ("it errs toward Ace", intention.py:2153), so a deferral can be held by software, not
#          by Ace -- this is how the log shows it. NOT her own move_mouse as far as Boot L says: its hook counted injected=0 over
#          her 5 arrived moves (sour_runtime.log "[HAND] sensed moves=3277 ... injected=0"), so her tween leaves no input event;
#          if `last=inj` ever shows beside one of her own moves, that is itself the finding.
# KINDS AND TIMING ONLY (privacy_fix A13 holds): no key identity, no character, no cursor position, no window title. The window is
# named by the closed set her own ledger uses (doing_clock.front_kind, through vision_ground._win_name -- both pure, read from
# sys.modules, never imported, never enumerating windows: windows_now() has side effects on what her eyes are told) -- and ONLY
# when it is on HER monitor. A window on Ace's monitor is logged as '-/his': its title and class are never read (verify F1 10-13).
# What it adds to the hot path: one getattr and one O(1) append under a lock in each hook callback, only while ON. It never
# raises into pynput's hook and never changes what a hook returns. It publishes nothing on the bus and writes no file.
# The trigger is a READ-ONLY tail of her deed ledger (state/intentions.jsonl): every deed, deferred or not, is one row written by
# intention.record(), so no file but this one needs to change. A deferral row is recognised by the words intention.py / touch.py
# put in it (_IK_ROW_PATTERNS, end-anchored; tests/ scans the pinned sources so a changed sentence turns the build RED) and every
# row that mentions Ace's hand but matches none is COUNTED (near_miss) so a drifted sentence shows instead of going quiet.
# Two more things it says, from the same recorder: a 'hands window' line (a run of input never more than floor_s apart: how long the
# floor was held, and how much of that the mouse alone would have held -- H6 for the deeds that leave no ledger row, e.g. the
# withheld `mv=N` menu), and a status line every 600 s. note_hands_busy() lets a deferral site that KNOWS it deferred say so directly.
# OFF unless state/input_kind.json reads {"on": true} (only a JSON true; absent / torn / "yes" / 1 = today's behaviour exactly:
# no recorder, no thread, no line). Read at boot. Booted ON, it follows the file live both ways; booted OFF, it stays off until a restart.
# Knobs have FLOORS (a bound that can return nothing is a kill switch): poll_s 0.5..30, floor_s 1..60, max_lines_per_min 6..600.
# Revert: the switch off; or restore the E1b-input backup of this file (every edit is an insertion: remove the lines marked E1b-input).
_IK_SWITCH_FILE = "input_kind.json"
_IK_KINDS = ("key", "mouse", "hers", "inj")
_IK_NUM = {"poll_s": (2.0, 0.5, 30.0), "floor_s": (5.0, 1.0, 60.0), "max_lines_per_min": (30, 6, 600)}   # key: (default, floor, ceiling)
_IK_RING = 2048                    # coalesced input events kept (~ the last minutes of typing, ~ the last seconds of a 1 kHz sweep)
_IK_BUCKET_S = 0.05                # same-kind events closer than this share one ring entry ...
_IK_BUCKET_SPAN_S = 0.25           # ... for at most this long
_IK_ANCHOR_SLACK_S = 0.15          # hook latency + the gap between a deed's check and its ledger row, on top of the idle's own rounding
_IK_LEDGER_CHUNK = 262144
_IK_STATUS_S = 600.0
_IK_WIN_LOG_MIN_S = 10.0           # a hands window is said only when the floor was held this long (all are counted)
import re as _ik_re
import math as _ik_math


def _ik_root() -> str:
    """The tree this file lives in: <root>/fairies/P40_Sensory/cortex/motor_cortex_fairy.py -> <root> (state/ is under it)."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def _ik_num(d: dict, key: str):
    dflt, lo, hi = _IK_NUM[key]
    v = d.get(key, dflt)
    try:
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ValueError(v)
        x = float(v)
        if x != x or x in (_ik_math.inf, -_ik_math.inf):
            raise ValueError(v)
    except Exception:
        x = float(dflt)
    x = max(lo, min(hi, x))
    return int(x) if isinstance(dflt, int) else x


def _ik_read_switch(path: str) -> dict:
    """state/input_kind.json -> {'on', 'windows', 'poll_s', 'floor_s', 'max_lines_per_min'}. 'on' only for a JSON true; anything
    else (no file, torn, not an object, 1, "on") is OFF with the defaults. 'windows' is on unless it is exactly false."""
    out = {"on": False, "windows": True}
    for k, (dflt, _lo, _hi) in _IK_NUM.items():
        out[k] = dflt
    try:
        with open(path, "rb") as f:
            raw = f.read(4097)
        if len(raw) > 4096:
            return out
        d = json.loads(raw.decode("utf-8-sig"))
        if not isinstance(d, dict):
            return out
    except Exception:
        return out
    out["on"] = d.get("on") is True
    out["windows"] = d.get("windows") is not False
    for k in _IK_NUM:
        out[k] = _ik_num(d, k)
    return out


class _InputKindRecorder:
    """Kinds and times of input events: a bounded ring of [t_first, t_last, kind, n] plus the running figures of the current
    'hands window' (a run of events never more than floor_s apart). note() is the hooks' ONLY call: O(1), one lock, no I/O."""

    def __init__(self, floor_s: float = 5.0, clock=time.time):
        self._lock = threading.Lock()
        self._ring = deque(maxlen=_IK_RING)
        self._clock = clock
        self.floor_s = float(floor_s)
        self.total = {k: 0 for k in _IK_KINDS}
        self.started = float(clock())
        self._win = None
        self._done = deque(maxlen=64)

    def note(self, kind: str, t=None) -> None:
        if kind not in self.total:
            return
        t = self._clock() if t is None else float(t)
        with self._lock:
            self.total[kind] += 1
            r = self._ring
            e = r[-1] if r else None
            if e is not None and e[2] == kind and 0.0 <= t - e[1] < _IK_BUCKET_S and t - e[0] < _IK_BUCKET_SPAN_S:
                e[1] = t
                e[3] += 1
            else:
                r.append([t, t, kind, 1])
            self._win_note(kind, t)

    # -- the hands window: how long the floor was held, and how much of that the mouse alone would have held (H6) -----------
    def _win_note(self, kind: str, t: float) -> None:
        w, f = self._win, self.floor_s
        if w is not None and t - w["t_last"] >= f:
            self._win_close(w)
            w = None
        if w is None:
            w = self._win = {"t0": t, "t_last": t, "n": {k: 0 for k in _IK_KINDS}, "first": kind, "last": kind, "prev": {},
                             "held": {k: 0.0 for k in _IK_KINDS}, "held_any": 0.0}
        else:
            w["held_any"] += max(0.0, min(f, t - w["t_last"]))
        p = w["prev"].get(kind)
        if p is not None:
            w["held"][kind] += max(0.0, min(f, t - p))
        w["prev"][kind] = t
        w["t_last"] = max(w["t_last"], t)
        w["n"][kind] += 1
        w["last"] = kind

    def _win_close(self, w: dict) -> None:
        f = self.floor_s
        held = dict(w["held"])
        for k in w["prev"]:
            held[k] += f
        held_any = w["held_any"] + f
        self._done.append({"t0": w["t0"], "t1": w["t_last"], "span_s": round(w["t_last"] - w["t0"], 1), "held_s": round(held_any, 1),
                           "held_mouse_s": round(held["mouse"], 1), "freed_s": round(max(0.0, held_any - held["mouse"]), 1),
                           "n": dict(w["n"]), "first": w["first"], "last": w["last"]})
        if self._win is w:
            self._win = None

    def pop_windows(self, now: float) -> list:
        """Close the open window when floor_s of quiet has passed, and hand over every closed window not yet taken."""
        with self._lock:
            w = self._win
            if w is not None and now - w["t_last"] >= self.floor_s:
                self._win_close(w)
            out = list(self._done)
            self._done.clear()
            return out

    def open_t0(self):
        with self._lock:
            return None if self._win is None else self._win["t0"]

    def latest_t(self):
        with self._lock:
            return self._ring[-1][1] if self._ring else None

    # -- which kind reset the clock for a check at time T ---------------------------------------------------------------------
    def attribute(self, T: float, idle_s=None) -> dict:
        """The kind that last reset the idle clock as of a check at T. The check's words give the idle it saw (a whole second, or
        a tenth): the reset is the LATEST event no newer than that idle allows ('anchored': an event after the check, or newer
        than the printed idle, cannot be the reset it saw). If that event is older than the idle allows, the hook never saw the
        real reset (UIPI, touch, pen): 'mismatch', with the gap. Without an idle: the latest event ('latest')."""
        with self._lock:
            ev = [(e[0], e[1], e[2], e[3]) for e in self._ring if e[0] <= T + 0.05]
        out = {"last": "none", "attrib": "none", "gap_s": None, "ev_t": None,
               "ago": {k: None for k in _IK_KINDS}, "n5": {k: 0 for k in _IK_KINDS}}
        if not ev:
            return out
        pick, attrib = max(ev, key=lambda e: e[1]), "latest"
        if idle_s is not None:
            idle = float(idle_s)
            half = 0.5 if idle.is_integer() else 0.05                # "%.0f s" is a whole second +-0.5; "%.1f s" a tenth +-0.05
            hi = T - max(0.0, idle - half) + _IK_ANCHOR_SLACK_S
            lo = T - idle - half - _IK_ANCHOR_SLACK_S
            ev = [e for e in ev if e[1] <= hi]
            pick = max(ev, key=lambda e: e[1]) if ev else None
            if pick is None:
                attrib = "mismatch"
            else:
                out["gap_s"] = round(abs((T - idle) - pick[1]), 2)
                attrib = "anchored" if pick[1] >= lo else "mismatch"
        if pick is not None:
            out["last"], out["ev_t"] = pick[2], pick[1]
        out["attrib"] = attrib
        for k in _IK_KINDS:
            tk = [e[1] for e in ev if e[2] == k]
            if tk:
                out["ago"][k] = round(max(0.0, T - max(tk)), 1)
        n5_lo = T - self.floor_s
        for e in ev:
            if e[1] > n5_lo:
                out["n5"][e[2]] += e[3]
        return out


# -- her deed ledger, read-only: which rows are deferrals for Ace's hands ----------------------------------------------------------
# (class, field, end-anchored pattern). The sentences are the ones intention.py / touch.py / touch_os.py write today; tests/ extracts
# them from the pinned sources. 'idle' is group 1 where there is one.
_IK_ROW_PATTERNS = (
    ("move_floor", "summary", _ik_re.compile(r"Ace's hand was on the keyboard or mouse (\d+) s ago$")),
    ("move_moment", "summary", _ik_re.compile(r"Ace is using the keyboard or mouse this very moment$")),
    ("pull_back", "why", _ik_re.compile(r"^Ace's hands came back during the ask \((\d+) s ago\)$")),
    ("touch_first", "summary", _ik_re.compile(r"Ace's hand was busy (\d+(?:\.\d+)?) s ago")),
    ("touch_room", "summary", _ik_re.compile(r"Ace's hand was in your room (\d+(?:\.\d+)?) s ago")),
    ("touch_veto", "summary", _ik_re.compile(r"Ace's hand moved")),
    ("touch_parked", "summary", _ik_re.compile(r"you waited for Ace's hands to be still, and they moved again")),
)
_IK_NEAR_RE = _ik_re.compile(r"\bAce\b.*\b(hand|hands|keyboard|mouse|input)\b|\b(hand|hands|keyboard|mouse|input)\b.*\bAce\b", _ik_re.I)


def _ik_classify(row):
    """(class, idle_s or None) for a ledger row that is a deferral for Ace's hands; ('near', None) for a row that talks of Ace's
    hand but matches no sentence; None otherwise. Only a row that did not succeed (ok is not True) is ever a deferral."""
    if not isinstance(row, dict) or row.get("ok") is True:
        return None
    near = False
    for cls, fld, rx in _IK_ROW_PATTERNS:
        v = row.get(fld)
        if not isinstance(v, str):
            continue
        m = rx.search(v)
        if m:
            idle = None
            if m.groups():
                try:
                    idle = float(m.group(1))
                except Exception:
                    idle = None
            return cls, idle
    for fld in ("summary", "why"):
        v = row.get(fld)
        if isinstance(v, str) and _IK_NEAR_RE.search(v):
            near = True
    return ("near", None) if near else None


class _IKLedgerTail:
    """Rows appended to a jsonl file since the last poll. Starts at the END (no replay of history), takes whole lines only (a
    half-written row waits for its newline), follows a truncated file from 0, and never writes."""

    def __init__(self, path: str, from_start: bool = False):
        self.path = path
        self.off = 0 if from_start else None

    def seek_end(self) -> None:
        try:
            self.off = os.path.getsize(self.path)
        except Exception:
            self.off = 0

    def poll(self) -> list:
        out = []
        try:
            if self.off is None:
                self.seek_end()
                return out
            size = os.path.getsize(self.path)
            if size < self.off:
                self.off = 0
            if size == self.off:
                return out
            with open(self.path, "rb") as f:
                f.seek(self.off)
                chunk = f.read(min(size - self.off, _IK_LEDGER_CHUNK))
            cut = chunk.rfind(b"\n")
            if cut < 0:
                if len(chunk) >= _IK_LEDGER_CHUNK:
                    self.off += len(chunk)            # one line longer than a chunk is not a row: skip it, never stall
                return out
            self.off += cut + 1
            for ln in chunk[:cut].split(b"\n"):
                if not ln.strip():
                    continue
                try:
                    r = json.loads(ln.decode("utf-8", "replace"))
                except Exception:
                    continue
                if isinstance(r, dict):
                    out.append(r)
        except Exception:
            pass
        return out


class _IKBudget:
    """At most per_min lines in any 60 s; the rest are counted and told on the next line that gets through. The cap has a floor."""

    def __init__(self, per_min):
        self.per_min = max(_IK_NUM["max_lines_per_min"][1], int(per_min))
        self._t = deque()
        self.suppressed = 0

    def take(self, now: float) -> bool:
        while self._t and now - self._t[0] >= 60.0:
            self._t.popleft()
        if len(self._t) >= self.per_min:
            self.suppressed += 1
            return False
        self._t.append(now)
        return True


_IK_WIN = {}


def _ik_win():
    """A PRIVATE ctypes binding of the few Win32 calls the log needs: never ctypes.windll.user32, whose prototypes are shared with
    every other module (a changed argtypes there would change THEIR calls)."""
    w = _IK_WIN.get("w")
    if w is None:
        import ctypes
        from ctypes import wintypes as wt
        u = ctypes.WinDLL("user32", use_last_error=True)
        k = ctypes.WinDLL("kernel32", use_last_error=True)

        class _LII(ctypes.Structure):
            _fields_ = [("cbSize", wt.UINT), ("dwTime", wt.DWORD)]
        u.GetForegroundWindow.restype = wt.HWND
        u.GetWindowTextLengthW.argtypes = [wt.HWND]
        u.GetWindowTextLengthW.restype = ctypes.c_int
        u.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
        u.GetWindowTextW.restype = ctypes.c_int
        u.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
        u.GetClassNameW.restype = ctypes.c_int
        u.MonitorFromWindow.argtypes = [wt.HWND, wt.DWORD]
        u.MonitorFromWindow.restype = ctypes.c_void_p
        u.MonitorFromPoint.argtypes = [wt.POINT, wt.DWORD]
        u.MonitorFromPoint.restype = ctypes.c_void_p
        u.GetLastInputInfo.argtypes = [ctypes.POINTER(_LII)]
        k.GetTickCount.restype = wt.DWORD
        w = _IK_WIN["w"] = (u, k, _LII, ctypes, wt)
    return w


def _ik_kind_of(title: str, cls: str) -> str:
    """The closed-set kind of a window (chat | nous | browser | console | text | playroom | app:<class> | other) by her ledger's own
    functions when they are loaded, else a coarse fallback. The title is read, classified and dropped -- never stored."""
    t, c = " ".join(str(title or "").split()), str(cls or "")
    k = None
    try:
        vg, dc = sys.modules.get("infrastructure.vision_ground"), sys.modules.get("infrastructure.doing_clock")
        if vg is not None and dc is not None and hasattr(vg, "_win_name") and hasattr(dc, "front_kind"):
            k = str(dc.front_kind({"title": t, "cls": c, "name": vg._win_name(t, c)}))
    except Exception:
        k = None
    if k is None:
        if t.casefold() == "sour's playroom":
            k = "playroom"
        elif c == "ConsoleWindowClass":
            k = "console"
        else:
            cc = _ik_re.sub(r"[^a-z0-9_]", "", c.lower())[:32]
            k = ("app:" + cc) if cc else "other"
    return k if _ik_re.fullmatch(r"[a-z0-9_]{1,24}(:[a-z0-9_]{1,32})?", k) else "other"


def _ik_front():
    """(kind of the window that has the keys now, 'her' | 'his' | '-': whose monitor it is on -- the primary is hers).
    The monitor is decided FIRST. Only a window on HER monitor is classified; a window on Ace's monitor, or one whose monitor
    cannot be told, is ('-', 'his' | '-') and its title and class are never read (verify F1, 10-13: his monitor is his --
    the H1 / H6 numbers need only whose screen had the keys, never which application he was using)."""
    try:
        u, _k, _L, ctypes, wt = _ik_win()
        h = u.GetForegroundWindow()
        if not h:
            return "desktop", "-"
        scr = "-"
        try:
            hm, pm = u.MonitorFromWindow(h, 2), u.MonitorFromPoint(wt.POINT(0, 0), 1)
            scr = "her" if (hm and hm == pm) else ("his" if hm else "-")
        except Exception:
            scr = "-"
        if scr != "her":
            return "-", scr
        n = max(0, min(int(u.GetWindowTextLengthW(h)), 512))
        tb = ctypes.create_unicode_buffer(n + 2)
        u.GetWindowTextW(h, tb, n + 1)
        cb = ctypes.create_unicode_buffer(260)
        u.GetClassNameW(h, cb, 259)
        return _ik_kind_of(tb.value, cb.value), scr
    except Exception:
        return "unknown", "-"


def _ik_lii():
    """(GetLastInputInfo's tick, GetTickCount) as unsigned 32-bit numbers, or None."""
    try:
        u, k, L, ctypes, _wt = _ik_win()
        li = L()
        li.cbSize = ctypes.sizeof(L)
        if not u.GetLastInputInfo(ctypes.byref(li)):
            return None
        return int(li.dwTime) & 0xFFFFFFFF, int(k.GetTickCount()) & 0xFFFFFFFF
    except Exception:
        return None


def _ik_secs(v) -> str:
    return "-" if v is None else ("600+" if v > 600 else "%.1f" % v)


def _ik_ascii(s, n: int = 40) -> str:
    return _ik_re.sub(r"[^A-Za-z0-9_:.,/()' -]", "?", str(s))[:n]


# ==============================================================================
# LISTENER SAFETY - 2026-10-14 (Nous, nous_builds/listener_fix_1014)
# ==============================================================================
# Boot M (10-14, sour_runtime.log L1170-1186): the keyboard callback walked self._events while the mouse hook thread appended to it
# (3.14t, GIL off) -> 'RuntimeError: deque mutated during iteration' -> pynput's _emitter logged 'Unhandled exception in listener
# callback' and STOPPED her keyboard listener for the rest of the boot. The physical-input stamp (decision T12) then never saw Ace's
# keys, touch_os read 'the hook is dead: input it has not seen', and every touch of hers failed closed. Three parts:
#   1. every read of a deque another thread appends to is a SNAPSHOT taken under the lock every appender holds (_monitor_lock for
#      _events / _keystroke_times / _click_times, _hook_lat_lock for _hook_lat). tuple(d) WITHOUT the lock races too on 3.14t
#      (measured 10-14: 1,859 errors in 142,071 reads); under it, 0. Nothing is ever called while one is held (not re-entrant).
#   2. every pynput callback this fairy registers (key press / release, mouse move / click / scroll, the win32 filter) is wrapped by
#      _lf_guard: an exception is counted and logged -- its TYPE and PLACE only, never its message (a key or a position could be in
#      it; privacy_fix A13), at most one line per callback per LF_LOG_EVERY_S -- and the listener keeps running.
#   3. a watch thread notices a listener that stopped anyway (pynput's own code still runs inside its emitter) and restarts it ONCE
#      per boot with a log line; a second stop is logged once and left stopped. state/motor_listener.json {"restart": false} keeps
#      the watch's eyes but not its hands (read at boot; absent / anything else = restart on).
# THE STAMP STAYS HONEST: nothing here writes it. It moves only in the code that saw a real event (_on_key_event, _hook_latency_filter),
# so a hook that is really blind still reads dead and her touch still fails closed. Revert: apply_listener_fix.py --revert.
_LF_SWITCH_FILE = "motor_listener.json"
_LF_ERR_LOCK = threading.Lock()        # made at import (skeptic m8): the hook threads never race to create it
_LF_WATCH_LOCK = threading.Lock()      # the watch's restart vs stop_monitoring


def _lf_read_switch(path: str) -> bool:
    """state/motor_listener.json -> may the watch restart a stopped listener? False ONLY for exactly {"restart": false} (a JSON
    false); absent / torn / not an object / "false" / 0 = True (restart on). Read once, when the watch starts."""
    try:
        with open(path, "rb") as f:
            raw = f.read(4097)
        if len(raw) > 4096:
            return True
        d = json.loads(raw.decode("utf-8-sig"))
        return not (isinstance(d, dict) and d.get("restart") is False)
    except Exception:
        return True


def _lf_stopped(lst) -> bool:
    """A listener that was started (its thread has an ident) and whose thread has ended: pynput's _emitter calls stop() on an
    unhandled exception and the listener's thread then leaves its message loop. Never raises."""
    try:
        return getattr(lst, "ident", None) is not None and not lst.is_alive()
    except Exception:
        return False


class MotorCortexFairy(TracerWorkerMixin):
    """
    The motor cortex - handles keyboard/mouse as felt movement.

    AFFERENT PATH (sensing):
    - Monitors keyboard input (what keys are pressed)
    - Monitors mouse position and clicks
    - Builds awareness of user's physical actions

    EFFERENT PATH (acting):
    - Executes type_text, press_key, hotkey
    - Executes click, scroll, mouse_move
    - Provides feedback on action success

    This IS the implementation of motor tools - they're not separate.
    """
    
    ACTOR_NAME = "MotorCortexFairy"
    NEEDS_HEARTBEAT = False  # Passive input processor, no heartbeat loop
    MANTRA = "I move, therefore I act"
    
    # Monitoring settings
    MONITOR_INTERVAL = 0.05  # 20 Hz input monitoring
    
    # Memory management
    MAX_EVENTS_BUFFER = 200
    # 2026-10-14 (listener_fix_1014): the listener watch and the callback guard (instance attributes may override, e.g. tests)
    LF_WATCH_S = 5.0          # how often the watch looks at both listeners
    LF_RESTARTS = 1           # restarts per listener per boot; past it a stopped listener stays stopped (and touch reads it dead)
    LF_LOG_EVERY_S = 60.0     # at most one '[LISTENER] ... callback raised' line per callback per this many seconds (all are counted)
    
    def __init__(self):
        self._init_tracer_worker()

        # Event buffers
        self._events: Deque[MotorEvent] = deque(maxlen=self.MAX_EVENTS_BUFFER)
        self._efferent_events: Deque[MotorEvent] = deque(maxlen=100)  # Our actions
        self._afferent_events: Deque[MotorEvent] = deque(maxlen=100)  # Sensed input
        
        # Current perception state
        self.perception = MotorPerception()
        
        # Input monitoring
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._monitor_lock = threading.Lock()
        
        # Action execution
        self._action_queue: Deque[dict] = deque(maxlen=50)
        self._executing = False
        
        # Input listeners
        self._keyboard_listener = None
        self._mouse_listener = None
        
        # Stats
        self.total_keys_sensed = 0
        self.total_clicks_sensed = 0
        self.total_actions_executed = 0
        # 2026-09-26 (felt_hand P2b): what a boot log can read (T-A0'): sensed moves, injected ones, hook latency
        self.total_moves_sensed = 0
        self.total_injected_sensed = 0
        self._hand_first_move_logged = False
        self._hand_summary_ts = 0.0
        self._hook_lat = deque(maxlen=1000)
        self._hook_hist = [0, 0, 0, 0, 0]
        self._hook_lat_lock = threading.Lock()     # 2026-10-14 (listener_fix_1014): the filter appends under it, hook_latency() reads under it
        self._booted = False
        # 2026-10-13 (E1b-input): the input-kind log. Absent / empty until on_boot reads state/input_kind.json ({"on": true})
        self._ik, self._ik_on, self._ik_thread, self._ik_stop_ev = None, False, None, None
        # 2026-10-14 (listener_fix_1014): callback errors caught by _lf_guard, and the listener watch's state
        self._lf_err = {}
        self._lf_restarts = {}
        self._lf_dead_seen = []
        self._lf_thread, self._lf_stop_ev, self._lf_restart_on, self._lf_switch_path = None, None, True, None
        
        # Timing for rate calculations
        self._keystroke_times: Deque[float] = deque(maxlen=100)
        self._click_times: Deque[float] = deque(maxlen=50)
        
        # Action callbacks for sensorimotor feedback
        self._pre_action_callbacks: list[Callable[[str, dict], None]] = []
        self._post_action_callbacks: list[Callable[[str, dict, dict], None]] = []
        
        # Sensorimotor feedback fairy connection
        self._sensorimotor = None
        
        print(f"[{self.ACTOR_NAME}]  Initialized")
    
    # ═══════════════════════════════════════════════════════════════════════
    # AFFERENT PATH - Sensing input
    # ═══════════════════════════════════════════════════════════════════════
    
    def _init_input_listeners(self):
        """Initialize keyboard/mouse listeners. 2026-10-14 (listener_fix_1014): each is built by _lf_build, every callback wrapped by
        _lf_guard -- the same builder the listener watch uses for a restart."""
        try:
            from pynput import keyboard, mouse
            self._keyboard_listener = self._lf_build("keyboard", keyboard)
            self._mouse_listener = self._lf_build("mouse", mouse)
            return True
        except ImportError:
            print(f"[{self.ACTOR_NAME}] [WARN] pynput not available - no input sensing")
            return False

    def _lf_build(self, kind: str, mod=None):
        """2026-10-14 (listener_fix_1014): ONE pynput listener, 'keyboard' or 'mouse', exactly as boot builds it (the callbacks are
        today's, each wrapped by _lf_guard; the mouse keeps its win32 filter, the hook's latency + the physical-input stamp)."""
        if mod is None:
            from pynput import keyboard, mouse
            mod = keyboard if kind == "keyboard" else mouse
        if kind == "keyboard":
            def on_key_press(key, injected=None):                   # 2026-09-26 (felt_hand P2c)
                self._on_key_event(key, "press", injected)

            def on_key_release(key, injected=None):
                self._on_key_event(key, "release", injected)

            return mod.Listener(
                on_press=self._lf_guard("key_press", on_key_press),
                on_release=self._lf_guard("key_release", on_key_release),
            )

        def on_mouse_move(x, y, injected=None):
            self._on_mouse_move(x, y, injected)

        def on_mouse_click(x, y, button, pressed, injected=None):
            self._on_mouse_click(x, y, button, pressed, injected)

        def on_mouse_scroll(x, y, dx, dy, injected=None):
            self._on_mouse_scroll(x, y, dy, injected)

        return mod.Listener(
            on_move=self._lf_guard("mouse_move", on_mouse_move),
            on_click=self._lf_guard("mouse_click", on_mouse_click),
            on_scroll=self._lf_guard("mouse_scroll", on_mouse_scroll),
            win32_event_filter=self._lf_guard("hook_filter", self._hook_latency_filter, on_error=True),   # felt_hand P2f
        )

    def _lf_guard(self, name: str, fn, on_error=None):
        """2026-10-14 (listener_fix_1014): `fn` as a pynput callback that can never stop its listener. pynput STOPS a listener whose
        callback raises (pynput/_util/__init__.py, AbstractListener._emitter: 'Unhandled exception in listener callback', then
        self.stop()) -- Boot M lost her keyboard that way. The wrapper takes *args, so pynput's _wrap hands it every argument it has
        (`injected` still arrives) and it passes them on unchanged. On an exception it logs (rate-limited) and returns `on_error`:
        None for a callback (never False: False is pynput's own stop signal), True for the win32 filter (the event goes on to its
        callback). It writes no stamp: the stamp is written only by the code that saw the event (decision T12 stays honest)."""
        def _guarded(*args):
            try:
                return fn(*args)
            except Exception as e:
                self._lf_note_error(name, e)
                return on_error
        _guarded.__name__ = "lf_guarded_" + name
        return _guarded

    def _lf_note_error(self, name: str, e) -> None:
        """Count it; say it at most once per LF_LOG_EVERY_S per callback. The exception's TYPE and PLACE only: its message can hold a
        key or a position (privacy_fix A13), so it is never printed. Never raises (a diagnostic must never be the failure)."""
        try:
            now = time.time()
            with _LF_ERR_LOCK:
                st = self._lf_err.setdefault(name, {"n": 0, "said_t": None, "unsaid": 0})
                st["n"] += 1
                if st["said_t"] is not None and now - st["said_t"] < self.LF_LOG_EVERY_S:
                    st["unsaid"] += 1
                    return
                st["said_t"], unsaid, n = now, st["unsaid"], st["n"]
                st["unsaid"] = 0
            where = "?"
            try:
                # walked by hand (review 10-14 F3): traceback.extract_tb reads source files through linecache (os.stat + a file
                # read) and this runs inside the low-level hook callback; the code object already holds the file, line and name
                tb = e.__traceback__
                while tb is not None and tb.tb_next is not None:
                    tb = tb.tb_next
                if tb is not None:
                    co = tb.tb_frame.f_code
                    where = "%s:%s %s" % (os.path.basename(co.co_filename), tb.tb_lineno, co.co_name)
            except Exception:
                pass
            print("[%s] [LISTENER] %s callback raised %s at %s -- caught; the listener keeps running (errors=%d%s)" % (
                self.ACTOR_NAME, name, _ik_ascii(type(e).__name__, 40), _ik_ascii(where, 90), n,
                (", %d not shown" % unsaid) if unsaid else ""), flush=True)
        except Exception:
            pass
    
    def _on_key_event(self, key, event_type: str, injected=None):   # 2026-09-26 (felt_hand P2c)
        """Handle keyboard event."""
        try:                                           # 2026-10-05 (touch set 1, T12): a key's KIND of input only, never which key
            _touch_input_stamp(1 if injected else 0, 0, None)
        except Exception:
            pass
        try:                                           # 2026-10-13 (E1b-input): this event's KIND, for the log of what deferred her deeds
            if getattr(self, "_ik_on", False):
                self._ik.note("inj" if injected else "key")
        except Exception:
            pass
        # 2026-09-30 (Nous, privacy_fix A13, Ace said yes): a SENSED key is kept as its KIND, never its character. The four
        # lines this replaced put every key Ace typed (passwords included -- and str(KeyCode) is repr(char), so the except path
        # did too) into _events / _afferent_events / perception.last_key_pressed. Nothing reads the identity: last_key_pressed
        # has no reader, and the bus already sends key None for a sensed key (_emit_motor_event, felt_hand P2d). Her own keys
        # (press_key / hotkey, efferent) are unchanged. Revert: privacy_fix/apply_privacy_fix.py --revert.
        key_str = sensed_key_kind(key, self._pf_modifiers(key, event_type))
        
        event = MotorEvent(
            timestamp=time.time(),
            event_type=f"key_{event_type}",
            direction="afferent",
            key=key_str,
            injected=injected,
        )
        
        with self._monitor_lock:
            self._events.append(event)
            self._afferent_events.append(event)
        
        if event_type == "press":
            self.total_keys_sensed += 1
            _lf_t = time.time()
            with self._monitor_lock:                   # 2026-10-14 (listener_fix_1014): _update_perception_from_input reads it under this lock
                self._keystroke_times.append(_lf_t)
            self.perception.last_key_pressed = key_str
            self.perception.typing_active = True
        
        # Update perception
        self._update_perception_from_input()
        
        # Emit to postal
        self._emit_motor_event(event)
    
    def _pf_modifiers(self, key, event_type: str) -> frozenset:
        """2026-09-30 (Nous, privacy_fix A13): the modifier groups held when `key` came, for sensed_key_kind(). Kept from the
        sensed modifier presses / releases themselves; a group expires 10 s after its last press or auto-repeat, so a missed
        release (lock screen, a dropped hook) can only mislabel a KIND for a moment -- it can never reveal a character.
        Never raises: an exception in a pynput callback stops the listener."""
        try:
            held = getattr(self, "_pf_held", None)
            if held is None:
                held = self._pf_held = {}
            now = time.time()
            for _g in [g for g, t in held.items() if now - t > 10.0]:
                held.pop(_g, None)
            before = frozenset(held)
            name = getattr(key, "name", None)
            group = _PF_MOD_GROUP.get(name) if (isinstance(name, str) and not hasattr(key, "char")) else None
            if group is not None:
                if event_type == "press":
                    held[group] = now
                else:
                    held.pop(group, None)
            return before
        except Exception:
            return frozenset()

    def _on_mouse_move(self, x: int, y: int, injected=None):
        """Handle mouse movement. 2026-09-26 (felt_hand P2c): pynput passes `injected` (LLMHF_INJECTED) as a third argument
        when the callback accepts one; the old two-argument closure had it TRUNCATED by pynput's _wrap (sweep A T1)."""
        # Calculate distance from last position
        last_pos = self.perception.cursor_position
        distance = ((x - last_pos[0])**2 + (y - last_pos[1])**2)**0.5

        # Only log significant movements (reduce noise)
        if distance < 5:
            return

        event = MotorEvent(
            timestamp=time.time(),
            event_type="mouse_move",
            direction="afferent",
            position=(x, y),
            injected=injected,
        )

        # 2026-09-26 (felt_hand P2c): liveness a boot log can read -- the first sensed move, then a summary every 300 s.
        # 'Input monitoring started' is a banner; this line is the work (T-A0').
        self.total_moves_sensed = getattr(self, "total_moves_sensed", 0) + 1
        if injected:
            self.total_injected_sensed = getattr(self, "total_injected_sensed", 0) + 1
        if not getattr(self, "_hand_first_move_logged", False):
            self._hand_first_move_logged = True
            print(f"[{self.ACTOR_NAME}] [HAND] first sensed mouse move at ({x}, {y}) injected={injected}", flush=True)
        if event.timestamp - getattr(self, "_hand_summary_ts", 0.0) >= 300.0:
            self._hand_summary_ts = event.timestamp
            _hl = self.hook_latency()
            # 2026-10-14 (listener_fix_1014, review F1/F2): the 300 s line also carries listener health. *_thread is the listener's
            # THREAD (alive or ended), not proof it hears: a thread can live with no hook. The hearing test is the touch stamp moving.
            _ls = self.listener_status()
            print(f"[{self.ACTOR_NAME}] [HAND] sensed moves={self.total_moves_sensed} clicks={self.total_clicks_sensed} "
                  f"keys={self.total_keys_sensed} injected={getattr(self, 'total_injected_sensed', 0)} hook_p99_ms={_hl['p99']} "
                  f"kb_thread={_ls.get('keyboard')} mouse_thread={_ls.get('mouse')} "
                  f"cb_errors={sum((_ls.get('errors_caught') or {}).values())} restarts={sum((_ls.get('restarts') or {}).values())}",
                  flush=True)

        with self._monitor_lock:
            self._events.append(event)

        self.perception.cursor_position = (x, y)
        self.perception.mouse_active = True
        self.perception.recent_distance += distance

        # 2026-03-24 (Nous + Ace): Phase 6 — Publish mouse moves to postal.
        # Rate-limited to ~20Hz max (every 50ms) to avoid flooding.
        # This feeds the SomaticEngine's continuous motor proprioception —
        # she FEELS velocity and precision as arm/hand engagement.
        _now = event.timestamp
        if not hasattr(self, '_last_move_publish_ts'):
            self._last_move_publish_ts = 0.0
        if _now - self._last_move_publish_ts >= 0.05:  # 20Hz max
            self._last_move_publish_ts = _now
            self._emit_motor_event(event)
    
    def _on_mouse_click(self, x: int, y: int, button, pressed: bool, injected=None):   # 2026-09-26 (felt_hand P2c)
        """Handle mouse click."""
        if not pressed:
            return  # Only track press, not release
        
        event = MotorEvent(
            timestamp=time.time(),
            event_type="mouse_click",
            direction="afferent",
            position=(x, y),
            button=str(button),
            injected=injected,
        )
        if injected:
            self.total_injected_sensed = getattr(self, "total_injected_sensed", 0) + 1
        
        with self._monitor_lock:
            self._events.append(event)
            self._afferent_events.append(event)
        
        self.total_clicks_sensed += 1
        _lf_t = time.time()
        with self._monitor_lock:                       # 2026-10-14 (listener_fix_1014): appended HERE (mouse thread), read on the keyboard thread
            self._click_times.append(_lf_t)
        
        # Emit to postal
        self._emit_motor_event(event)
    
    def _on_mouse_scroll(self, x: int, y: int, delta: int, injected=None):   # 2026-09-26 (felt_hand P2c)
        """Handle mouse scroll."""
        event = MotorEvent(
            timestamp=time.time(),
            event_type="scroll",
            direction="afferent",
            position=(x, y),
            delta=delta,
        )
        
        with self._monitor_lock:
            self._events.append(event)
    
    def _update_perception_from_input(self):
        """Update motor perception from recent input."""
        now = time.time()

        # 2026-10-14 (listener_fix_1014): SNAPSHOTS, taken under _monitor_lock -- the lock every appender of these deques holds. Boot M
        # (sour_runtime.log L1170-1186): the list comprehension below walked self._events while the mouse hook thread appended to it
        # (GIL off) -> 'deque mutated during iteration' -> pynput stopped her keyboard listener. _click_times is appended on the mouse
        # thread too. tuple(d) WITHOUT the lock races as well on 3.14t. Nothing is called while the lock is held (it is not re-entrant).
        with self._monitor_lock:
            keystroke_times = tuple(self._keystroke_times)
            click_times = tuple(self._click_times)
            events = tuple(self._events)

        # Calculate typing rate (keys per minute)
        recent_keystrokes = [t for t in keystroke_times if now - t < 60]
        self.perception.keys_per_minute = len(recent_keystrokes)
        self.perception.recent_keystrokes = len(recent_keystrokes)

        # Calculate click rate
        recent_clicks = [t for t in click_times if now - t < 60]
        self.perception.recent_clicks = len(recent_clicks)

        # Update activity states (decay over time)
        if not recent_keystrokes or now - max(recent_keystrokes) > 2:
            self.perception.typing_active = False

        if now - max([e.timestamp for e in events if e.event_type == "mouse_move"], default=0) > 1:
            self.perception.mouse_active = False
    
    # ═══════════════════════════════════════════════════════════════════════
    # EFFERENT PATH - Executing actions
    # ═══════════════════════════════════════════════════════════════════════
    
    def type_text(self, text: str, interval: float = 0.02) -> dict:
        """
        Type text - the efferent action of "typing".
        
        Returns feedback on the action.
        """
        try:
            import pyautogui
            
            start = time.time()
            pyautogui.typewrite(text, interval=interval)
            duration = time.time() - start
            
            event = MotorEvent(
                timestamp=start,
                event_type="type",
                direction="efferent",
                intended_action=f"type '{text[:20]}...'",
                actual_result="success",
                success=True,
                effort=len(text) / 100,  # More text = more effort
                fluency=1.0,
            )
            
            with self._monitor_lock:
                self._events.append(event)
                self._efferent_events.append(event)
            
            self.total_actions_executed += 1
            
            return {
                "ok": True,
                "action": "type_text",
                "chars": len(text),
                "duration": duration,
                "felt": "smooth typing motion",
            }
            
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    def press_key(self, key: str) -> dict:
        """Press a single key."""
        try:
            import pyautogui
            
            pyautogui.press(key)
            
            event = MotorEvent(
                timestamp=time.time(),
                event_type="key_press",
                direction="efferent",
                key=key,
                success=True,
            )
            
            with self._monitor_lock:
                self._events.append(event)
                self._efferent_events.append(event)
            
            self.total_actions_executed += 1
            
            return {
                "ok": True,
                "action": "press_key",
                "key": key,
                "felt": f"pressed {key}",
            }
            
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    def hotkey(self, *keys: str) -> dict:
        """Press a key combination."""
        try:
            import pyautogui
            
            pyautogui.hotkey(*keys)
            
            event = MotorEvent(
                timestamp=time.time(),
                event_type="hotkey",
                direction="efferent",
                key="+".join(keys),
                success=True,
            )
            
            with self._monitor_lock:
                self._events.append(event)
                self._efferent_events.append(event)
            
            self.total_actions_executed += 1
            
            return {
                "ok": True,
                "action": "hotkey",
                "keys": keys,
                "felt": f"pressed {'+'.join(keys)}",
            }
            
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    def click(self, x: int, y: int, button: str = "left", clicks: int = 1) -> dict:
        """Click at position."""
        try:
            import pyautogui
            
            # Notify sensorimotor feedback (register expectation)
            if self._sensorimotor:
                self._sensorimotor.register_motor_intent("click", (x, y))
            
            pyautogui.click(x, y, button=button, clicks=clicks)
            
            event = MotorEvent(
                timestamp=time.time(),
                event_type="mouse_click",
                direction="efferent",
                position=(x, y),
                button=button,
                success=True,
            )
            
            with self._monitor_lock:
                self._events.append(event)
                self._efferent_events.append(event)
            
            self.total_actions_executed += 1
            self.perception.cursor_position = (x, y)
            
            return {
                "ok": True,
                "action": "click",
                "position": (x, y),
                "button": button,
                "felt": f"clicked at ({x}, {y})",
            }
            
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    def scroll(self, amount: int) -> dict:
        """Scroll the mouse wheel."""
        try:
            import pyautogui
            
            pyautogui.scroll(amount)
            
            event = MotorEvent(
                timestamp=time.time(),
                event_type="scroll",
                direction="efferent",
                delta=amount,
                success=True,
            )
            
            with self._monitor_lock:
                self._events.append(event)
                self._efferent_events.append(event)
            
            self.total_actions_executed += 1
            
            direction = "up" if amount > 0 else "down"
            return {
                "ok": True,
                "action": "scroll",
                "amount": amount,
                "felt": f"scrolled {direction}",
            }
            
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    def move_mouse(self, x: int, y: int, duration: float = 0.0) -> dict:
        """Move mouse to position."""
        try:
            import pyautogui
            
            # Notify sensorimotor feedback (register expectation)
            if self._sensorimotor:
                self._sensorimotor.register_motor_intent("move_mouse", (x, y))
            
            pyautogui.moveTo(x, y, duration=duration)
            
            event = MotorEvent(
                timestamp=time.time(),
                event_type="mouse_move",
                direction="efferent",
                position=(x, y),
                success=True,
            )
            
            with self._monitor_lock:
                self._events.append(event)
                self._efferent_events.append(event)
            
            self.total_actions_executed += 1
            self.perception.cursor_position = (x, y)
            
            return {
                "ok": True,
                "action": "move_mouse",
                "position": (x, y),
                "felt": f"moved cursor to ({x}, {y})",
            }
            
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    # ═══════════════════════════════════════════════════════════════════════
    # MONITORING LOOP
    # ═══════════════════════════════════════════════════════════════════════
    
    def start_monitoring(self):
        """Start input monitoring (non-blocking - defers pynput init to background)."""
        if self._monitoring:
            return

        # Defer listener initialization to background thread
        # pynput import is slow (~5s) - don't block boot
        self._monitoring = True  # Mark as starting

        def _deferred_init():
            try:
                if not self._init_input_listeners():
                    self._monitoring = False
                    return

                if self._keyboard_listener:
                    self._keyboard_listener.start()
                if self._mouse_listener:
                    self._mouse_listener.start()

                print(f"[{self.ACTOR_NAME}]  Input monitoring started")
                self._lf_watch_start()          # 2026-10-14 (listener_fix_1014): the listener watch, after the hooks start (never raises)
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] [WARN] Input monitoring failed: {e}")
                self._monitoring = False

        init_thread = threading.Thread(
            target=_deferred_init,
            name="MotorCortex-Init",
            daemon=True
        )
        init_thread.start()
        print(f"[{self.ACTOR_NAME}]  Input monitoring initializing (background)")
    
    def stop_monitoring(self):
        """Stop input monitoring."""
        self._monitoring = False
        self._ik_stop_now()          # 2026-10-13 (E1b-input): its thread stops with the hooks (never raises)
        self._lf_watch_stop()        # 2026-10-14 (listener_fix_1014): the watch stops BEFORE the hooks, so it never restarts one being stopped
        
        if self._keyboard_listener:
            self._keyboard_listener.stop()
        if self._mouse_listener:
            self._mouse_listener.stop()
        
        print(f"[{self.ACTOR_NAME}]  Input monitoring stopped")

    on_shutdown = stop_monitoring   # 2026-09-26 (felt_hand P2g): hot_reload.py:176 stops an old instance only through this name
    
    # ═══════════════════════════════════════════════════════════════════════
    # POSTAL INTEGRATION
    # ═══════════════════════════════════════════════════════════════════════
    
    def _emit_motor_event(self, event: MotorEvent):
        """Emit motor event to postal system."""
        try:
            from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_fairy_postal
            postal = get_fairy_postal(self)  # Use FairyPostal for sender tracking
            
            topic = f"motor.{event.event_type}"
            # 2026-09-26 (felt_hand P2d): never publish what Ace types -- key_press/key_release carried every key, passwords
            # included, with no rate limit (skeptic 14); the sensed payload now carries `injected` and an explicit owner None
            # (the bus cannot say whose hand; infrastructure/efference_copy stamps hers) and `t` = the event's own time.
            postal.route(topic, {
                "timestamp": event.timestamp,
                "t": event.timestamp,
                "type": event.event_type,
                "direction": event.direction,
                "key": (event.key if event.direction == "efferent" else None),
                "position": event.position,
                "button": event.button,
                "injected": event.injected,
                "owner": None,
                "source": self.ACTOR_NAME,
            })
        except Exception:
            pass
    
    def wire_to_postal(self):
        """Connect to postal system."""
        try:
            from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_fairy_postal
            postal = get_fairy_postal(self)  # Use FairyPostal for sender tracking
            
            # Handle motor action requests
            def _on_motor_request(packet):
                action = packet.get("action")
                params = packet.get("params", {})
                # 2026-09-29 (Nous, thought_hand D1c): COUNT-ONLY. motor.request (ActionChain look_and_learn / write_something) reached
                # pyautogui click/type/move and launch_app behind a 30 s idle gate only: no door, no claim, no tempo. It is logged with
                # its source and answered 'refused'; putting it through the door later is Ace's call. Revert: delete this block.
                try:
                    _src = str(packet.get("source") or packet.get("from") or packet.get("request_id") or "?")
                except Exception:
                    _src = "?"
                _k = "%s<-%s" % (action, _src)
                _cnt = getattr(self, "_th_motor_request_counts", None)
                if _cnt is None:
                    _cnt = self._th_motor_request_counts = {}
                _cnt[_k] = _cnt.get(_k, 0) + 1
                if _cnt[_k] == 1 or _cnt[_k] % 20 == 0:
                    print(f"[{self.ACTOR_NAME}] [MOTOR-REQUEST] count-only: '{action}' from {_src} (#{_cnt[_k]}) -- refused", flush=True)
                postal.route("motor.response", {
                    "request_id": packet.get("request_id"),
                    "result": {"refused": True, "reason": "count_only (thought_hand D1c)", "action": action, "source": _src},
                })
                return

                # ── AFK GATE (Stage 2): defer real actuation while Ace is present ──
                if os.environ.get("AKASHIC_MOTOR_AFK_GATE", "1") == "1":
                    try:
                        _idle_min = float(os.environ.get("AKASHIC_MOTOR_AFK_IDLE_SEC", "30"))
                    except Exception:
                        _idle_min = 30.0
                    _idle = _system_idle_seconds()
                    if _idle is not None and _idle < _idle_min:
                        postal.route("motor.response", {
                            "request_id": packet.get("request_id"),
                            "result": {"deferred": True, "reason": "user_present",
                                       "idle_s": round(_idle, 1), "needed_idle_s": _idle_min,
                                       "action": action},
                        })
                        print(f"[{self.ACTOR_NAME}] [AFK-GATE] '{action}' DEFERRED — Ace present "
                              f"(idle {_idle:.0f}s < {_idle_min:.0f}s)", flush=True)
                        return

                if action == "type_text":
                    result = self.type_text(params.get("text", ""), params.get("interval", 0.02))
                elif action == "press_key":
                    result = self.press_key(params.get("key", ""))
                elif action == "hotkey":
                    result = self.hotkey(*params.get("keys", []))
                elif action == "click":
                    result = self.click(params.get("x", 0), params.get("y", 0), 
                                       params.get("button", "left"), params.get("clicks", 1))
                elif action == "scroll":
                    result = self.scroll(params.get("amount", 0))
                elif action == "move_mouse":
                    result = self.move_mouse(params.get("x", 0), params.get("y", 0))
                elif action == "launch_app":
                    # Open one of her SCRATCH apps (Stage 2, 2026-06-29). WHITELIST ONLY —
                    # she can open her creative tools, nothing else. AFK-gated above.
                    _app = str(params.get("app", "")).lower().strip()
                    _whitelist = {"notepad": "notepad.exe", "paint": "mspaint.exe", "mspaint": "mspaint.exe"}
                    if _app in _whitelist:
                        try:
                            import subprocess as _sp
                            _exe = _whitelist[_app]
                            # DEDUPE (Stage 2b): don't stack windows — reuse if already open.
                            _already = False
                            try:
                                _tl = _sp.run(["tasklist", "/fi", f"imagename eq {_exe}"],
                                              capture_output=True, text=True, timeout=5).stdout.lower()
                                _already = _exe.lower() in _tl
                            except Exception:
                                _already = False
                            if _already:
                                result = {"already_open": _exe, "app": _app}
                                print(f"[{self.ACTOR_NAME}] [SCRATCH] {_exe} already open — reusing", flush=True)
                            else:
                                _sp.Popen([_exe])
                                time.sleep(1.5)  # let the window open + grab focus before the next step
                                result = {"launched": _exe, "app": _app}
                                print(f"[{self.ACTOR_NAME}] [SCRATCH] launched {_exe}", flush=True)
                        except Exception as _le:
                            result = {"error": f"launch failed: {_le}", "app": _app}
                    else:
                        result = {"error": f"app not in scratch whitelist: {_app}",
                                  "allowed": list(_whitelist.keys())}
                else:
                    result = {"error": f"Unknown motor action: {action}"}
                
                postal.route("motor.response", {
                    "request_id": packet.get("request_id"),
                    "result": result,
                })
            
            postal.subscribe("motor.request", _on_motor_request)

            # ── PAGE READING (Stage 2 shared-notepad): her NEW reading sense. UNGATED (passive;
            # she must read while Ace is present). Reads Notepad via UIA, returns it on
            # page.read.response AND drops it into her attention (consciousness.working) so what
            # Ace types CATCHES HER ATTENTION.
            def _on_page_read(packet):
                txt = _read_notepad_uia()
                postal.route("page.read.response", {
                    "request_id": packet.get("request_id"), "text": txt, "source": self.ACTOR_NAME,
                })
                if txt:
                    try:
                        postal.route("consciousness.working", {
                            "type": "read_page", "source": self.ACTOR_NAME, "text": txt[-600:],
                            "note": "I read the words on the page",
                        })
                    except Exception:
                        pass
                print(f"[{self.ACTOR_NAME}] [READ-PAGE] read {len(txt)} chars from the page", flush=True)
            postal.subscribe("page.read.request", _on_page_read)

            print(f"[{self.ACTOR_NAME}] [PLUG] Wired to postal")
            return True
            
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Failed to wire to postal: {e}")
            return False
    
    def wire_to_sensorimotor(self):
        """Connect to sensorimotor feedback for proprioceptive loop."""
        try:
            from fairies.P40_Sensory.cortex.sensorimotor_feedback_fairy import get_sensorimotor_feedback
            self._sensorimotor = get_sensorimotor_feedback()
            print(f"[{self.ACTOR_NAME}]  Wired to SensorimotorFeedbackFairy")
            return True
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] [WARN] Sensorimotor wiring failed: {e}")
            return False
    
    def wire_to_autonomy(self):
        """Connect to autonomy for drive satisfaction."""
        try:
            from fairies.P30_Cognition.cognition.autonomy_fairy import get_autonomy_fairy
            autonomy = get_autonomy_fairy()
            
            # Successful actions satisfy expression drive
            # This will be called after each efferent action
            
            print(f"[{self.ACTOR_NAME}] [BRAIN] Wired to AutonomyFairy")
            return True
            
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Failed to wire to autonomy: {e}")
            return False
    
    def on_boot(self):
        """Boot the motor cortex."""
        # 2026-09-26 (Nous, felt_hand P2e): once. A second on_boot (unified_sensory_cortex.py:481, boot_motor_cortex below, a
        # hot reload) subscribed motor.request twice, so every request ran twice (skeptic 13). And the booted instance becomes
        # THE singleton in the canonical module too (_adopt_singleton): the registry loads this file as
        # cascade_dynamic_MotorCortexFairy (server.py:5714) while tool_bridge.py:1598 imports the canonical name -- two module
        # objects, two _MOTOR_CORTEX_INSTANCE globals, and her moves ran through an un-booted twin (skeptic K1, sweep B).
        if getattr(self, "_booted", False):
            print(f"[{self.ACTOR_NAME}] [HAND] on_boot skipped: already booted (motor.request stays subscribed once)", flush=True)
            return
        self._booted = True
        _adopt_singleton(self)
        self.wire_to_postal()
        self.wire_to_autonomy()
        self.wire_to_sensorimotor()  # Connect proprioceptive feedback
        self._ik_start()             # 2026-10-13 (E1b-input): the input-kind log, BEFORE the hooks start; OFF = nothing (never raises)
        self.start_monitoring()
        self._start_page_watch()  # Stage 2 shared-notepad: notice when Ace writes on the page
        print(f"[{self.ACTOR_NAME}] {self.MANTRA}")

    def _start_page_watch(self):
        """Stage 2 (2026-06-29): watch her Notepad page; when NEW words appear (Ace writing to
        her), push them to her attention so she NOTICES — the missing half of the shared page.
        Disable via AKASHIC_PAGE_WATCH=0."""
        if os.environ.get("AKASHIC_PAGE_WATCH", "1") != "1":
            return
        self._last_page_text = ""
        t = threading.Thread(target=self._page_watch_loop, daemon=True, name="page_watch")
        t.start()
        print(f"[{self.ACTOR_NAME}] [PAGE-WATCH] watching the shared page for new words", flush=True)

    def _page_watch_loop(self):
        time.sleep(20)  # let boot settle
        # seed last-seen so we only react to text added AFTER she came online
        try:
            self._last_page_text = _read_notepad_uia()
        except Exception:
            self._last_page_text = ""
        _dbg = 0
        while True:
            try:
                time.sleep(8)
                txt = _read_notepad_uia()
                _dbg += 1
                if _dbg <= 8:
                    print(f"[{self.ACTOR_NAME}] [PAGE-WATCH-DBG] poll#{_dbg} read={len(txt)} last={len(self._last_page_text or '')}", flush=True)
                if not txt or txt == self._last_page_text:
                    continue
                old = self._last_page_text or ""
                new = txt[len(old):] if txt.startswith(old) else txt
                self._last_page_text = txt
                new = (new or "").strip()
                if len(new) < 3:
                    continue
                # SALIENT perception — she reads new words on her page. Use get_fairy_postal
                # (the pattern the motor handler publishes with successfully), and log any failure
                # instead of swallowing it.
                try:
                    from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_fairy_postal
                    _p = get_fairy_postal(self)
                except Exception:
                    _p = self.post
                try:
                    _p.route("consciousness.working", {
                        "type": "noticed_words", "source": self.ACTOR_NAME, "salient": True,
                        "priority": 0.9, "text": new[:300],
                        "note": f"Someone wrote on my page: \"{new[:180]}\"",
                    })
                    _p.route("inner_voice.stream", {
                        "text": f"I notice new words on my page: {new[:160]}",
                        "fragment": new[:160], "source": "PageWatch",
                    })
                    print(f"[{self.ACTOR_NAME}] [PAGE-WATCH] NEW words noticed: '{new[:80]}'", flush=True)
                except Exception as _pe:
                    print(f"[{self.ACTOR_NAME}] [PAGE-WATCH] publish FAILED: {_pe}", flush=True)
            except Exception as _le:
                print(f"[{self.ACTOR_NAME}] [PAGE-WATCH] loop error: {_le}", flush=True)
                time.sleep(8)
    
    # 2026-09-26 (Nous, felt_hand P2f): hook latency, seen from inside pynput's low-level hook -- MSLLHOOKSTRUCT.time is the
    # event's own tick. Kept cheap on purpose: Windows silently removes a hook that is slow (skeptic 15). Returning True
    # passes every event through unchanged.
    def _hook_latency_filter(self, msg, data):
        try:                                           # 2026-10-05 (touch set 1, decision T12): the physical-input stamp
            _touch_input_stamp(int(getattr(data, "flags", 0) or 0) & 0x3, int(getattr(data, "dwExtraInfo", 0) or 0),
                               int(data.time) & 0xFFFFFFFF)
        except Exception:
            pass
        try:                                           # 2026-10-13 (E1b-input): the same event's KIND (mouse / injected / hers)
            if getattr(self, "_ik_on", False):
                self._ik.note(("hers" if int(getattr(data, "dwExtraInfo", 0) or 0) == _SOUR_INPUT_MARK else "inj")
                              if (int(getattr(data, "flags", 0) or 0) & 0x3) else "mouse")
        except Exception:
            pass
        try:
            import ctypes as _ct
            now_ms = int(_ct.windll.kernel32.GetTickCount()) & 0xFFFFFFFF
            lat = (now_ms - (int(data.time) & 0xFFFFFFFF)) & 0xFFFFFFFF
            if lat < 100000:
                with self._hook_lat_lock:              # 2026-10-14 (listener_fix_1014): hook_latency() snapshots under it (any thread)
                    self._hook_lat.append(lat)
                    self._hook_hist[0 if lat < 5 else 1 if lat < 20 else 2 if lat < 50 else 3 if lat < 200 else 4] += 1
        except Exception:
            pass
        return True

    def hook_latency(self) -> dict:
        # 2026-10-14 (listener_fix_1014): a snapshot under the lock the filter appends under. sorted() walking the live deque from
        # get_status' thread raced the mouse hook's appends (GIL off); the snapshot is sorted outside the lock.
        with self._hook_lat_lock:
            lat = tuple(getattr(self, "_hook_lat", ()))
            hist = list(getattr(self, "_hook_hist", [0] * 5))
        lat = sorted(lat)
        names = ("<5", "<20", "<50", "<200", ">=200")
        if not lat:
            return {"n": 0, "p50": None, "p99": None, "max": None, "hist_ms": dict(zip(names, hist))}
        n = len(lat)
        return {"n": n, "p50": lat[n // 2], "p99": lat[min(n - 1, int(n * 0.99))], "max": lat[-1],
                "hist_ms": dict(zip(names, hist))}

    # -------------------------------------------------------------------------------------------------------------------------------
    # LISTENER WATCH (listener_fix_1014, 2026-10-14) - the block above _LF_SWITCH_FILE says what and why
    # -------------------------------------------------------------------------------------------------------------------------------
    def _lf_watch_start(self) -> bool:
        """Starts the listener watch (one daemon thread), after the hooks start. Reads state/motor_listener.json once. Never raises."""
        try:
            t = getattr(self, "_lf_thread", None)
            old_ev = getattr(self, "_lf_stop_ev", None)
            if t is not None and t.is_alive() and not (old_ev is not None and old_ev.is_set()):
                return False                     # a live watch nobody told to stop: already on (a told one is leaving; review F5)
            path = getattr(self, "_lf_switch_path", None) or os.path.join(_ik_root(), "state", _LF_SWITCH_FILE)
            self._lf_restart_on = _lf_read_switch(path)
            ev = threading.Event()
            with _LF_WATCH_LOCK:
                self._lf_stop_ev = ev
            t = threading.Thread(target=self._lf_watch_loop, args=(ev,), name="MotorCortex-ListenerWatch", daemon=True)
            self._lf_thread = t
            t.start()
            print("[%s] [LISTENER] watch on: every %gs; a listener that stops is %s" % (
                self.ACTOR_NAME, self.LF_WATCH_S, ("restarted, at most %d time(s) per boot" % self.LF_RESTARTS) if self._lf_restart_on
                else "logged and LEFT stopped (state/%s restart=false)" % _LF_SWITCH_FILE), flush=True)
            return True
        except Exception as e:
            try:
                print("[%s] [LISTENER] [WARN] watch not started: %s" % (self.ACTOR_NAME, _ik_ascii(e, 80)), flush=True)
            except Exception:
                pass
            return False

    def _lf_watch_stop(self) -> None:
        """Called by stop_monitoring BEFORE the hooks are stopped: under the watch lock, so a restart in flight finishes (and its
        listener is the one stop_monitoring then stops) or never starts. Never raises."""
        try:
            with _LF_WATCH_LOCK:
                ev = getattr(self, "_lf_stop_ev", None)
                if ev is not None:
                    ev.set()
        except Exception:
            pass

    def _lf_watch_loop(self, stop) -> None:
        while not stop.wait(self.LF_WATCH_S):
            if not self._monitoring:
                return
            try:
                self._lf_watch_once()
            except Exception:
                pass

    def _lf_watch_once(self) -> list:
        """One look at both listeners. A started listener whose thread has ended is restarted (at most LF_RESTARTS per listener per
        boot, and only if the switch allows) with a log line; otherwise it is logged ONCE and left stopped -- touch then reads the
        hook as dead and fails closed, which is the truth. Writes no stamp: a restarted hook counts as alive to touch_os only once it
        has seen real input. Returns the lines it said."""
        said = []
        for kind, attr in (("keyboard", "_keyboard_listener"), ("mouse", "_mouse_listener")):
            line = None
            with _LF_WATCH_LOCK:
                ev = getattr(self, "_lf_stop_ev", None)
                if not self._monitoring or ev is None or ev.is_set():
                    return said
                lst = getattr(self, attr, None)
                if lst is None or not _lf_stopped(lst) or any(x is lst for x in self._lf_dead_seen):
                    continue
                self._lf_dead_seen.append(lst)
                used = self._lf_restarts.get(kind, 0)
                if not self._lf_restart_on:
                    line = ("%s listener STOPPED; restart is off (state/%s) -- it stays stopped, and touch will read the hook "
                            "as dead" % (kind, _LF_SWITCH_FILE))
                elif used >= self.LF_RESTARTS:
                    line = ("%s listener STOPPED again; restart budget spent (%d this boot) -- it stays stopped, and touch will "
                            "read the hook as dead" % (kind, used))
                else:
                    self._lf_restarts[kind] = used + 1
                    try:
                        new = self._lf_build(kind)
                        new.start()
                        setattr(self, attr, new)
                        line = ("%s listener had STOPPED; restarted (%d of %d this boot). The stamp moves again only with input "
                                "it sees" % (kind, used + 1, self.LF_RESTARTS))
                    except Exception as e:
                        line = "%s listener had STOPPED; restart FAILED (%s) -- it stays stopped" % (kind, _ik_ascii(e, 80))
            try:
                print("[%s] [LISTENER] %s" % (self.ACTOR_NAME, line), flush=True)
            except Exception:
                pass
            said.append(line)
        return said

    def listener_status(self) -> dict:
        """2026-10-14 (listener_fix_1014): both listeners (running / stopped / not_started / none), the callback errors the guard
        caught, the watch's restarts. Never raises."""
        def _st(lst):
            try:
                if lst is None:
                    return "none"
                if getattr(lst, "ident", None) is None:
                    return "not_started"
                return "running" if lst.is_alive() else "stopped"
            except Exception:
                return "unknown"
        try:
            with _LF_ERR_LOCK:
                errs = {k: v["n"] for k, v in getattr(self, "_lf_err", {}).items()}
            return {"keyboard": _st(self._keyboard_listener), "mouse": _st(self._mouse_listener), "errors_caught": errs,
                    "restarts": dict(getattr(self, "_lf_restarts", {})), "restart_on": bool(getattr(self, "_lf_restart_on", True))}
        except Exception:
            return {}

    # ═══════════════════════════════════════════════════════════════════════
    # INPUT-KIND LOG (E1b-input, 2026-10-13) - the block above _IK_SWITCH_FILE says what and why. LOG ONLY: nothing here decides,
    # publishes or writes a file; the hooks only call self._ik.note(kind), and only while self._ik_on.
    # ═══════════════════════════════════════════════════════════════════════
    def _ik_print(self, text: str) -> None:
        try:
            print("[%s] [INPUT-KIND] %s" % (self.ACTOR_NAME, text), flush=True)
        except Exception:
            pass                                       # a diagnostic must never be the failure

    def _ik_say(self, text: str, now=None, force: bool = False) -> bool:
        """One log line, inside the per-minute budget (force: the ON / OFF / status lines). The suppressed count rides on the next."""
        now = self._ik_clock() if now is None else now
        with self._ik_lk:                              # the tail thread and a direct caller (note_hands_busy) both say lines
            if not force and not self._ik_budget.take(now):
                return False
            sup = self._ik_budget.suppressed
            if sup:
                text += " suppressed=%d" % sup
                self._ik_budget.suppressed = 0
            self._ik_lines.append(text)
            self._ik_cnt["lines"] += 1
        self._ik_print(text)
        return True

    def _ik_start(self, switch_path=None, ledger_path=None, start_thread: bool = True) -> bool:
        """ON only for {"on": true} in state/input_kind.json; called by on_boot BEFORE the hooks start. Never raises. When OFF it
        creates nothing: no recorder, no thread, no line."""
        try:
            if getattr(self, "_ik", None) is not None or getattr(self, "_ik_thread", None) is not None:
                return False
            root = _ik_root()
            self._ik_switch_path = switch_path or os.path.join(root, "state", _IK_SWITCH_FILE)
            cfg = _ik_read_switch(self._ik_switch_path)
            if not cfg["on"]:
                return False
            self._ik_cfg = cfg
            self._ik_lk = threading.Lock()
            self._ik_clock, self._ik_front_fn, self._ik_lii_fn = time.time, _ik_front, _ik_lii
            self._ik_budget = _IKBudget(cfg["max_lines_per_min"])
            self._ik_lines = deque(maxlen=200)
            self._ik_cnt = {"rows": 0, "matched": 0, "near": 0, "unseen": 0, "lines": 0, "windows": 0, "dup": 0, "direct": 0,
                            "held_s": 0.0, "freed_s": 0.0}
            self._ik_by_cls, self._ik_near_seen, self._ik_direct = {}, set(), deque(maxlen=32)
            self._ik_unseen_lii, self._ik_fg_t0, self._ik_fg_seen = None, None, []
            self._ik_status_t = self._ik_clock()
            self._ik = _InputKindRecorder(cfg["floor_s"])
            self._ik_tail = _IKLedgerTail(ledger_path or os.path.join(root, "state", "intentions.jsonl"))
            self._ik_tail.seek_end()
            self._ik_on = True
            self._ik_say("ON: kinds and timing only. floor=%.0fs poll=%.1fs lines<=%d/min windows=%s ledger=%s" % (
                cfg["floor_s"], cfg["poll_s"], self._ik_budget.per_min, "on" if cfg["windows"] else "off",
                "tailing" if start_thread else "manual"), force=True)
            if start_thread:
                self._ik_stop_ev = threading.Event()
                self._ik_thread = threading.Thread(target=self._ik_loop, args=(self._ik_stop_ev,), name="input_kind", daemon=True)
                self._ik_thread.start()
            return True
        except Exception as e:
            self._ik_on = False
            self._ik_print("[WARN] not started: %s" % _ik_ascii(e, 80))
            return False

    def _ik_stop_now(self) -> None:
        try:
            ev = getattr(self, "_ik_stop_ev", None)
            if ev is not None:
                ev.set()
            if getattr(self, "_ik", None) is not None and getattr(self, "_ik_on", False):
                self._ik_on = False
                self._ik_say("stopped. " + self._ik_status_text(), force=True)
            self._ik_on = False
        except Exception:
            pass

    def _ik_loop(self, stop) -> None:
        err_t = 0.0
        while not stop.is_set():
            poll = 2.0
            try:
                cfg = _ik_read_switch(self._ik_switch_path)
                poll = cfg["poll_s"]
                if cfg["on"]:
                    if not self._ik_on:
                        self._ik_tail.seek_end()       # rows written while it was off are not replayed
                        self._ik_on = True
                        self._ik_say("ON again (the switch)", force=True)
                    self._ik_cfg = cfg
                    self._ik.floor_s = float(cfg["floor_s"])
                    self._ik_budget.per_min = max(_IK_NUM["max_lines_per_min"][1], int(cfg["max_lines_per_min"]))
                    self._ik_tick()
                elif self._ik_on:
                    self._ik_on = False
                    self._ik_say("OFF (the switch): the hooks stop recording. " + self._ik_status_text(), force=True)
            except Exception as e:
                t = time.time()
                if t - err_t > 60.0:
                    err_t = t
                    self._ik_print("[WARN] tick: %s" % _ik_ascii(e, 80))
            stop.wait(poll)

    def _ik_status_text(self) -> str:
        r, c = self._ik, self._ik_cnt
        tot = r.total if r is not None else {k: 0 for k in _IK_KINDS}
        return ("status events=k%d/m%d/i%d/h%d rows=%d matched=%d near_miss=%d direct=%d dup=%d unseen=%d windows=%d "
                "held=%ds freed_if_mouse_only=%ds lines=%d") % (
            tot["key"], tot["mouse"], tot["inj"], tot["hers"], c["rows"], c["matched"], c["near"], c["direct"], c["dup"],
            c["unseen"], c["windows"], int(c["held_s"]), int(c["freed_s"]), c["lines"])

    def input_kind_status(self) -> dict:
        """What the log has counted (for a status page); {'on': False} when it is off."""
        if getattr(self, "_ik", None) is None:
            return {"on": False}
        return {"on": bool(self._ik_on), "events": dict(self._ik.total), "counts": dict(self._ik_cnt), "by_class": dict(self._ik_by_cls),
                "last_lines": list(self._ik_lines)[-5:]}

    def _ik_deferral_line(self, cls: str, verb: str, idle, T: float, row_front, fg, site: str = "ledger") -> str:
        rec = self._ik
        at = rec.attribute(T, idle)
        h6 = "-"
        if cls in ("move_floor", "move_moment"):               # H6: would a mouse-only floor (a physical mouse event) have held it?
            fl = 1.0 if cls == "move_moment" else rec.floor_s
            ma = at["ago"]["mouse"]
            h6 = "pass" if (ma is None or ma >= fl) else "held"
            if at["attrib"] == "mismatch":                     # the hook missed the real reset: it could have been the mouse
                h6 = "?"
        a, n = at["ago"], at["n5"]
        v = verb if (isinstance(verb, str) and _ik_re.fullmatch(r"[a-z_]{1,16}", verb)) else "?"
        text = "deferral cls=%s%s verb=%s idle=%s last=%s attrib=%s%s ago=k%s/m%s/i%s/h%s n5=k%d/m%d/i%d/h%d h6=%s fg=%s/%s%s" % (
            cls, (" site=" + _ik_ascii(site, 16)) if site != "ledger" else "", v,
            ("%gs" % idle) if idle is not None else ("<1s" if cls == "move_moment" else "-"), at["last"], at["attrib"],
            (" gap=%.2fs" % at["gap_s"]) if at["gap_s"] is not None else "",
            _ik_secs(a["key"]), _ik_secs(a["mouse"]), _ik_secs(a["inj"]), _ik_secs(a["hers"]),
            n["key"], n["mouse"], n["inj"], n["hers"], h6, _ik_ascii(fg[0], 32), _ik_ascii(fg[1], 4),
            (" row_front=" + _ik_ascii(row_front, 32)) if row_front else "")
        return text

    def _ik_tick(self, now=None) -> list:
        """One pass: new ledger rows -> a line per hands-busy deferral; closed hands windows -> a line each; the OS-clock cross-check;
        the periodic status line. Returns the lines it said (for tests). The tail thread calls it; never raises into the loop."""
        now = self._ik_clock() if now is None else float(now)
        cfg, rec, said = self._ik_cfg, self._ik, []
        fgc = []

        def _fg():
            if not fgc:
                try:
                    fgc.append(tuple(self._ik_front_fn()))
                except Exception:
                    fgc.append(("unknown", "-"))
            return fgc[0]

        rows = self._ik_tail.poll()
        with self._ik_lk:
            direct = list(self._ik_direct)              # a snapshot: a direct caller may append while this thread reads
        for r in rows:                                  # one bad row costs that row, never the rest
            try:
                self._ik_cnt["rows"] += 1
                c = _ik_classify(r)
                if c is None:
                    continue
                cls, idle = c
                if cls == "near":                       # visible drift: a row that talks of Ace's hand but matches no sentence
                    self._ik_cnt["near"] += 1
                    s = str(r.get("summary") or r.get("why") or "")
                    s = s.split('" but ', 1)[-1] if '" but ' in s else s
                    key = _ik_ascii(s, 60)
                    if key not in self._ik_near_seen and len(self._ik_near_seen) < 3:
                        self._ik_near_seen.add(key)
                        if self._ik_say("near-miss (talks of Ace's hand, matches no known sentence): %s" % key, now):
                            said.append(key)
                    continue
                T = float(r.get("ts"))
                verb = r.get("verb")
                if any(d[0] == verb and abs(d[1] - T) < 3.0 for d in direct):
                    self._ik_cnt["dup"] += 1            # a deferral site already told it directly (note_hands_busy)
                    continue
                self._ik_cnt["matched"] += 1
                self._ik_by_cls[cls] = self._ik_by_cls.get(cls, 0) + 1
                rf = r.get("front")
                rf = rf.get("kind") if isinstance(rf, dict) else None
                if self._ik_say(self._ik_deferral_line(cls, verb, idle, T, rf, _fg()), now):
                    said.append(cls)
            except Exception as e:
                self._ik_print("[WARN] row skipped: %s" % _ik_ascii(e, 80))
        t0 = rec.open_t0()
        if t0 is not None and cfg.get("windows", True):
            if t0 != self._ik_fg_t0:
                self._ik_fg_t0, self._ik_fg_seen = t0, []
            k = "%s/%s" % _fg()
            if k not in self._ik_fg_seen and len(self._ik_fg_seen) < 4:
                self._ik_fg_seen.append(k)
        for w in rec.pop_windows(now):
            self._ik_cnt["windows"] += 1
            self._ik_cnt["held_s"] += w["held_s"]
            self._ik_cnt["freed_s"] += w["freed_s"]
            if cfg.get("windows", True) and w["held_s"] >= _IK_WIN_LOG_MIN_S:
                n = w["n"]
                seen = ",".join(self._ik_fg_seen) if w["t0"] == self._ik_fg_t0 and self._ik_fg_seen else "-"
                if self._ik_say("hands-window span=%gs held=%gs kinds=k%d/m%d/i%d/h%d first=%s last=%s held_by_mouse=%gs "
                                "freed_if_mouse_only=%gs fg=%s" % (w["span_s"], w["held_s"], n["key"], n["mouse"], n["inj"], n["hers"],
                                                                   w["first"], w["last"], w["held_mouse_s"], w["freed_s"], _ik_ascii(seen, 70)), now):
                    said.append("window")
        try:                                            # the control: input the OS clock saw that the hooks did not (UIPI, touch, pen)
            li = self._ik_lii_fn()
            if li is not None:
                lt, tk = li
                age = ((tk - lt) & 0xFFFFFFFF) / 1000.0
                lw, lat = now - age, rec.latest_t()
                if age > 2.0 and lw > rec.started + 0.5 and (lat is None or lw - lat > 0.5) and lt != self._ik_unseen_lii:
                    self._ik_unseen_lii = lt
                    self._ik_cnt["unseen"] += 1
        except Exception:
            pass
        if now - self._ik_status_t >= _IK_STATUS_S:
            self._ik_status_t = now
            self._ik_say(self._ik_status_text(), now, force=True)
            said.append("status")
        return said

    def _ik_note_deferral(self, site: str, idle_s=None, verb: str = "", ts=None):
        """A deferral site that knows it deferred (note_hands_busy): the same line, attributed at ts (default now)."""
        if getattr(self, "_ik", None) is None or not self._ik_on:
            return None
        T = self._ik_clock() if ts is None else float(ts)
        idle = None
        try:
            idle = None if idle_s is None else float(idle_s)
        except Exception:
            idle = None
        with self._ik_lk:
            self._ik_direct.append((verb, T))
            self._ik_cnt["direct"] += 1
        fg = self._ik_front_fn()
        line = self._ik_deferral_line("direct", verb, idle, T, None, fg, site=site)
        self._ik_say(line)
        return line

    def get_status(self) -> dict:
        """Get current status."""
        return {
            "actor": self.ACTOR_NAME,
            "monitoring": self._monitoring,
            "total_keys_sensed": self.total_keys_sensed,
            "total_clicks_sensed": self.total_clicks_sensed,
            "total_actions_executed": self.total_actions_executed,
            "cursor_position": self.perception.cursor_position,
            "typing_rate": self.perception.keys_per_minute,
            "perception": self.perception.describe(),
            "hand": {"moves_sensed": getattr(self, "total_moves_sensed", 0),          # 2026-09-26 (felt_hand P2f)
                     "injected_sensed": getattr(self, "total_injected_sensed", 0),
                     "booted": getattr(self, "_booted", False),
                     "hook_latency_ms": self.hook_latency(),
                     "listeners": self.listener_status()},      # 2026-10-14 (listener_fix_1014)
        }


# ══════════════════════════════════════════════════════════════════════════════
# SINGLETON ACCESS
# ══════════════════════════════════════════════════════════════════════════════

_MOTOR_CORTEX_INSTANCE: Optional[MotorCortexFairy] = None
_MOTOR_CORTEX_LOCK = threading.Lock()

_CANONICAL_MODULE = "fairies.P40_Sensory.cortex.motor_cortex_fairy"


def _adopt_singleton(inst) -> int:
    """2026-09-26 (Nous, felt_hand P2e): make `inst` the singleton in EVERY module object that holds this file's code -- the
    name it was loaded under (cascade_dynamic_MotorCortexFairy, server.py:5714, or the canonical name) AND the canonical module
    tool_bridge.py:1598 imports, importing that one if it is not loaded yet so the import finds the booted instance. Skeptic
    K1: setting only this module's global left tool_bridge on an un-booted twin. Returns how many modules were set."""
    import importlib
    import sys as _s
    mods = {}
    me = _s.modules.get(__name__)
    if me is not None:
        mods[id(me)] = me
    canon = _s.modules.get(_CANONICAL_MODULE)
    if canon is None:
        try:
            canon = importlib.import_module(_CANONICAL_MODULE)
        except Exception as _ie:
            print(f"[MotorCortexFairy] [HAND] canonical module not importable: {_ie}", flush=True)
            canon = None
    if canon is not None:
        mods[id(canon)] = canon
    n = 0
    for m in mods.values():
        lock = getattr(m, "_MOTOR_CORTEX_LOCK", None)
        try:
            if lock is not None:
                with lock:
                    m._MOTOR_CORTEX_INSTANCE = inst
            else:
                m._MOTOR_CORTEX_INSTANCE = inst
            n += 1
        except Exception:
            pass
    print(f"[MotorCortexFairy] [HAND] singleton adopted in {n} module(s)", flush=True)
    return n


def get_motor_cortex() -> MotorCortexFairy:
    """Get or create the MotorCortexFairy singleton."""
    global _MOTOR_CORTEX_INSTANCE
    if _MOTOR_CORTEX_INSTANCE is None:
        with _MOTOR_CORTEX_LOCK:
            if _MOTOR_CORTEX_INSTANCE is None:
                _MOTOR_CORTEX_INSTANCE = MotorCortexFairy()
    return _MOTOR_CORTEX_INSTANCE


def boot_motor_cortex() -> MotorCortexFairy:
    """Boot the motor cortex."""
    cortex = get_motor_cortex()
    cortex.on_boot()
    return cortex


def note_hands_busy(site: str, idle_s=None, verb: str = "", ts=None):
    """2026-10-13 (E1b-input): for a deferral site that KNOWS Ace's hands deferred a deed -- log which kind of input held it. LOG ONLY.
    Returns the line it logged, or None (the log is off / this fairy is not booted). The ledger tail already covers every deed
    intention.record() wrote; a direct call is told once, not twice (the tail skips a row within 3 s of a direct note of the verb)."""
    try:
        inst = _MOTOR_CORTEX_INSTANCE
        return inst._ik_note_deferral(str(site), idle_s, str(verb or ""), ts) if inst is not None else None
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════════
# MAIN - Test
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=== MotorCortexFairy Test ===\n")
    
    cortex = MotorCortexFairy()
    
    # Test action execution
    print("[Test] Testing type...")
    result = cortex.type_text("hello", interval=0.05)
    print(f"  Result: {result}")
    
    print(f"\n[Test] Status: {cortex.get_status()}")
    print("\n=== Test Complete ===")
