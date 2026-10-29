"""doing_clock -- how long since she last DID something, the pull that builds while she is still, and one deed her hands could
reach for. 2026-10-01 (Nous, nous_builds/doing_clock).

Ace, 10-01: "her autonomy fairy should be the one that nudges her into action. it should be aware if she is in active ...
reflection is not movement, you can reflect on something over and over but it will only ever be a reflection of something she
might have done or is thinking of doing. its the doing she needs to be doing."
Measured (Boot E, 08:09-09:24, nous_builds/motivation_chain/MAPS.md): AutonomyFairy published 275 wantings; its cortex wantings
were musings (4 of 166 action-shaped) with an empty tool_hint; autonomy.wanting.acted_upon had 0 publishers, so loop_closures
stayed 0; the intent ask never saw a drive and answered none 22 of 33 times. Her ledger (state/intentions.jsonl, 09-19..10-01):
121 ok look/move/open/say deeds; between two deeds less than 3 h apart: median 414 s, p75 765 s, p90 1902 s.

THE SWITCH -- state/doing_clock.json, re-read when it changes (mtime + size). No file, a file that does not parse, or no key
means today's behaviour in every caller.
  {"on": true}               every piece below on, body_cost in "log" mode
  {"<piece>": true|false}    one piece on or off, overriding "on". Only a JSON true turns a piece on ("true", 1 do not)
     clock       AutonomyFairy keeps the doing clock: a "doing" block in autonomy_state.json, state/consciousness/doing_live.json
                 every drive-loop pass, one [DoingClock] line when something changes (else at most once a minute)
     restless    body_feel.body_line() carries one plain clause about her stillness once the pull passes clause_at
     wanting     past wanting_at the fairy's published wanting names a deed: look/move/open + a window on her screen or a
                 region her eyes labelled, or a goal she wrote herself (never 'say', never a fairy-made 'remember')
     ask_v2      intention.ask() uses the v2 wording (no 'nothing' brake; drives, stillness, windows, the leaning deed)
     loop_close  after each ok deed the fairy publishes autonomy.wanting.acted_upon; the served drive settles for settle_s
  "body_cost": "off" | "log" | "decline"   log = numbers and would_decline in the log line only; decline = past the line no
                 deed wanting is published and the v2 ask says 'not now' is an honest answer
  numbers (optional, clamped): ramp_s 900 [300, 3600], clause_at 0.35 [0.1, 0.9], wanting_at 0.5 [0.2, 0.95],
     settle_s 300 [60, 1800], ask_tokens 16 [8, 32], ado_at 0.12 [0, 1], slope_at 0.02 [0, 1] (allostatic load per 10 min)
  "send": "shadow" | "live"  2026-10-12 (engines_e1 11a/11b): her internal send button -- see 'the internal send button' at the
                 end of this file. ONLY those two exact strings turn it on; "on": true never does.

THE CLOCK  seconds since her last ok look/move/open/say row in the ledger, or since her process started when no deed came after
           it (a deed from an earlier boot is history, not stillness). 'remember' is not on the clock: it is the reflection
           Ace named. Rows whose summary says the deed was blocked (the same phrases intention._seed_prof skips) do not count.
THE PULL   restless = min(1, clock / ramp_s) * (0.6 + 0.4 * d), d = her strongest drive (prefixes merged, the goal queue's echo
           'goal' left out, floor 0.15, clamped to 1). With d = 0.40 it reaches clause_at 0.35 at ~414 s (the ledger's median
           gap) and wanting_at 0.50 at ~592 s. 0 while the heartbeat says she is asleep. A deed resets the clock, so the pull.
Revert: delete this file -- every caller's import fails and runs today's path.
"""
from __future__ import annotations

import json
import os
import random
import re
import sys                                             # 2026-10-05 (pull_ask): _sour_council_shared
import threading
import time
from collections import deque
from typing import Dict, List, Optional, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
SWITCH_FILE = os.path.join(_ROOT, "state", "doing_clock.json")
LEDGER = os.path.join(_ROOT, "state", "intentions.jsonl")
AUTONOMY_FILE = os.path.join(_ROOT, "state", "consciousness", "autonomy_state.json")
LIVE_FILE = os.path.join(_ROOT, "state", "consciousness", "doing_live.json")
HEARTBEAT = os.path.join(_ROOT, "state", "consciousness", "heartbeat.json")

PIECES = ("clock", "restless", "wanting", "ask_v2", "loop_close")
DEED_VERBS = ("look", "move", "open", "say")
ECHO_DRIVES = frozenset({"goal"})
DRIVE_FLOOR = 0.15                     # SomaticMind publishes a reward drive only above 0.15 (SomaticMindFairy/fairy.py:1345)
LIVE_MAX_AGE_S = 90.0                  # the drive loop passes every ~10 s (76 [WANTING-DIAG] lines in Boot F's first 12.5 min)
DRIVES_MAX_AGE_S = 300.0               # autonomy_state.json is rewritten every 1-3 min (measured 10-01: 11:22:14 -> 11:25:16)
HEARTBEAT_MAX_AGE_S = 120.0
NOVELTY_S = 300.0                      # intention._NOVELTY_S: the same verb+object inside 300 s is deferred anyway
HOLD_S = 300.0                         # a deed the fairy leans toward is held this long, so the nudge is one thing, not a shuffle
PENDING_MAX_AGE_S = 900.0
_TAIL_BYTES = 256 * 1024
_SKIP = ("hand is on the mouse", "hand was on the keyboard", "this very moment", "took the mouse back", "eyes were busy",
         "did not answer", "did not work", "hand to your hand")          # intention._seed_prof: not deeds
_NUM = {"ramp_s": (900.0, 300.0, 3600.0), "clause_at": (0.35, 0.1, 0.9), "wanting_at": (0.5, 0.2, 0.95),
        "settle_s": (300.0, 60.0, 1800.0), "ask_tokens": (16, 8, 32), "ado_at": (0.12, 0.0, 1.0), "slope_at": (0.02, 0.0, 1.0),
        # 2026-10-01 (Ace): the nudge "normally goes unspoken unless she chooses to" -- the deed wanting's intensity stays
        # below Autopilot's voluntary-speech bypass (0.75, AutopilotFairy/fairy.py:204), so restlessness moves her hands
        # quietly; she can still talk about what she did if she chooses. nudge_cap 1.0 lets the nudge speak.
        "nudge_cap": (0.74, 0.1, 1.0)}


# ── the switch ──────────────────────────────────────────────────────────────────────────────────────────────────────────
_SW = {"key": None, "data": {}}
_SW_LOCK = threading.Lock()


def _switch() -> Dict:
    try:
        st = os.stat(SWITCH_FILE)
    except OSError:
        return {}
    key = (st.st_mtime_ns, st.st_size)
    with _SW_LOCK:
        if key != _SW["key"]:
            try:
                with open(SWITCH_FILE, "rb") as f:
                    d = json.loads(f.read().decode("utf-8"))
                _SW["data"], _SW["key"] = (d if isinstance(d, dict) else {}), key
            except Exception:
                _SW["data"], _SW["key"] = {}, None           # torn or bad: today's path now, read again next call
        return _SW["data"]


def piece(name: str) -> bool:
    d = _switch()
    v = d.get(name)
    if isinstance(v, bool):
        return v
    return d.get("on") is True


def body_cost_mode() -> str:
    d = _switch()
    v = d.get("body_cost")
    if v in ("off", "log", "decline"):
        return v
    if v is False:
        return "off"
    return "log" if d.get("on") is True else "off"


def any_on() -> bool:
    return any(piece(p) for p in PIECES) or body_cost_mode() != "off"


def num(key: str):
    dflt, lo, hi = _NUM[key]
    v = _switch().get(key, dflt)
    try:
        if isinstance(v, bool):
            raise ValueError(v)
        x = float(v)
        if x != x:
            raise ValueError(v)
    except Exception:
        x = float(dflt)
    x = max(lo, min(hi, x))
    return int(x) if isinstance(dflt, int) else x


# ── when she woke ───────────────────────────────────────────────────────────────────────────────────────────────────────
def _proc_start() -> Optional[float]:
    try:
        import ctypes
        from ctypes import wintypes
        k = ctypes.windll.kernel32
        k.GetCurrentProcess.restype = wintypes.HANDLE
        ft = [wintypes.FILETIME() for _ in range(4)]
        if k.GetProcessTimes(k.GetCurrentProcess(), *[ctypes.byref(x) for x in ft]):
            t = ((ft[0].dwHighDateTime << 32) | ft[0].dwLowDateTime) / 1e7 - 11644473600.0
            if 0.0 < t <= time.time() + 5.0:
                return t
    except Exception:
        pass
    return None


BORN = _proc_start() or time.time()


# ── her ledger ──────────────────────────────────────────────────────────────────────────────────────────────────────────
_LED = {"key": None, "rows": []}
_LED_LOCK = threading.Lock()


def _ledger_rows(path: Optional[str] = None) -> List[Dict]:
    p = path or LEDGER
    try:
        st = os.stat(p)
    except OSError:
        return []
    key = (p, st.st_mtime_ns, st.st_size)
    with _LED_LOCK:
        if key == _LED["key"]:
            return _LED["rows"]
    try:
        with open(p, "rb") as f:
            f.seek(max(0, st.st_size - _TAIL_BYTES))
            raw = f.read()
        lines = raw.decode("utf-8", "replace").splitlines()
        if st.st_size > _TAIL_BYTES:
            lines = lines[1:]
        rows = []
        for ln in lines:
            try:
                r = json.loads(ln)
            except Exception:
                continue                                 # a row being appended right now: the next read sees it whole
            if isinstance(r, dict):
                rows.append(r)
    except Exception:
        return []
    with _LED_LOCK:
        _LED["key"], _LED["rows"] = key, rows
    return rows


# 2026-10-05 (Nous, pull_ask T; Ace's rule): a 'say' her quiet-cycle speaker would never voice is not a deed: it resets no
# clock and closes no loop. Measured (Boot G, doing_clock/results T8 + MAP s4): rows 254 and 279, object '.', ok True -- each
# reset the clock and closed a loop (log lines 112861, 196613), and neither was ever spoken. Skeptic F3 (10-05): the first rule
# (< 2 letters or digits) still counted 'ok' / 'hmm' / "it's..." -- lines the speaker drops too (sour_council_driver.py:964,
# `len(_line) >= 8`). So the rule IS the speaker's floor: fewer than 8 characters, or fewer than 2 letters or digits. The
# ledger keeps the rows; this only stops counting them (and intention.execute books a new one as a no-op while the clock is on).
TRIVIAL_SAY_MIN_ALNUM = 2
SAY_MIN_CHARS = 8                                      # = her quiet-cycle speaker's floor, sour_council_driver.py:964


def trivial_say(obj) -> bool:
    s = " ".join(str(obj or "").split())
    return len(s) < SAY_MIN_CHARS or sum(1 for ch in s if ch.isalnum()) < TRIVIAL_SAY_MIN_ALNUM


# 2026-10-05 (Nous, touch_screen set 1; FS12.2, decision T15): a CHECKED touch hit (ok True) is a deed -- it resets her doing
# clock and closes a waiting want. Skeptic M2 (10-05): decided by the ROW, never by the switch NOW. Touch writes ok True only for
# a press made while its switch was on, so a hit stays a deed after the session ends and her clock never jumps back. Only for a
# caller asking for every deed (DEED_VERBS, or a superset such as _close_loops' + 'remember'); a narrower filter (pull_ask's
# PULL_REPEAT_VERBS) is never widened. Touch never enters deed_candidates. No touch rows in her ledger = today.
_TOUCH_VERBS = ("tap", "double_tap", "hold")


def _touch_deed(r: Dict, verbs) -> bool:
    try:
        return r.get("verb") in _TOUCH_VERBS and set(DEED_VERBS) <= set(verbs)
    except Exception:
        return False


def is_deed(r: Dict, verbs=DEED_VERBS) -> bool:
    if not isinstance(r, dict) or r.get("ok") is not True or (r.get("verb") not in verbs and not _touch_deed(r, verbs)):
        return False
    try:
        float(r.get("ts"))
    except Exception:
        return False
    if r.get("verb") == "say" and trivial_say(r.get("object")):    # 2026-10-05 (pull_ask T): no words, no deed
        return False
    sm = str(r.get("summary") or "")
    return not any(k in sm for k in _SKIP)


def _deed(r: Dict) -> Dict:
    return {"ts": float(r["ts"]), "verb": str(r.get("verb")), "object": " ".join(str(r.get("object") or "").split())[:120]}


def last_deed(path: Optional[str] = None, verbs=DEED_VERBS) -> Optional[Dict]:
    for r in reversed(_ledger_rows(path)):
        if is_deed(r, verbs):
            return _deed(r)
    return None


def deeds_after(ts: float, path: Optional[str] = None, verbs=DEED_VERBS) -> List[Dict]:
    return [_deed(r) for r in _ledger_rows(path) if is_deed(r, verbs) and float(r["ts"]) > float(ts)]


def recent_pairs(now: Optional[float] = None, path: Optional[str] = None, window_s: float = NOVELTY_S) -> set:
    now = time.time() if now is None else float(now)
    out = set()
    for r in _ledger_rows(path):
        try:
            if now - float(r.get("ts")) < window_s and r.get("decision") == "allow":
                out.add((str(r.get("verb")), " ".join(str(r.get("object") or "").split()).lower()))
        except Exception:
            continue
    return out


# ── drives, body ────────────────────────────────────────────────────────────────────────────────────────────────────────
def drives_view(drives) -> List[Tuple[str, float]]:
    """Her drives as numbers under her substrate's own names, strongest first -- never argmax'd into 'she wants X'."""
    vals: Dict[str, float] = {}
    for key, v in (drives or {}).items() if isinstance(drives, dict) else ():
        name = str(key)
        for pre in ("positive.", "pain."):
            if name.startswith(pre):
                name = name[len(pre):]
                break
        if not name or name in ECHO_DRIVES:
            continue
        try:
            x = float(v)
        except (TypeError, ValueError):
            continue
        if x != x or x < DRIVE_FLOOR:
            continue
        vals[name] = max(vals.get(name, 0.0), x)
    return sorted(vals.items(), key=lambda kv: (-kv[1], kv[0]))


def drives_from_file(max_age_s: float = DRIVES_MAX_AGE_S, path: Optional[str] = None) -> Optional[Dict]:
    p = path or AUTONOMY_FILE
    try:
        if time.time() - os.path.getmtime(p) > max_age_s:
            return None
        with open(p, "rb") as f:
            d = json.loads(f.read().decode("utf-8"))
        dr = d.get("drives") if isinstance(d, dict) else None
        return dr if isinstance(dr, dict) else None
    except Exception:
        return None                                     # its writer (AutonomyFairy._export_state_file) is not atomic


def body_numbers(path: Optional[str] = None) -> Dict:
    p = path or HEARTBEAT
    try:
        age = time.time() - os.path.getmtime(p)
        if age > HEARTBEAT_MAX_AGE_S:
            return {}
        with open(p, "rb") as f:
            d = json.loads(f.read().decode("utf-8"))
        out = {"age_s": round(age, 1), "asleep": bool(d.get("asleep"))}
        for k, src in (("load", "allostatic_load"), ("ado", "ADO")):
            try:
                out[k] = round(float(d.get(src)), 4)
            except (TypeError, ValueError):
                pass
        return out
    except Exception:
        return {}


_LOAD = deque(maxlen=400)                              # (ts, allostatic load), fed by fairy_tick
_LOAD_LOCK = threading.Lock()


def note_load(ts: float, load) -> None:
    try:
        x = float(load)
    except (TypeError, ValueError):
        return
    with _LOAD_LOCK:
        _LOAD.append((float(ts), x))


def load_slope(now: Optional[float] = None, span_s: float = 600.0) -> Optional[float]:
    """Allostatic load change per 10 min over the last span_s; None with under 120 s of samples. The LEVEL is a within-boot
    odometer (it discharges only when COR and NE are both below baseline, chemistry_state.py:686-695), so the slope is the
    candidate cost signal, not the level (motivation_chain DESIGN B3, skeptic Q2)."""
    now = time.time() if now is None else float(now)
    with _LOAD_LOCK:
        pts = [(t, x) for t, x in _LOAD if now - t <= span_s]
    if len(pts) < 2 or pts[-1][0] - pts[0][0] < 120.0:
        return None
    return round((pts[-1][1] - pts[0][1]) / (pts[-1][0] - pts[0][0]) * 600.0, 4)


def would_decline(body: Dict, slope: Optional[float]) -> Tuple[bool, str]:
    why = []
    ado = body.get("ado")
    if ado is not None and ado >= num("ado_at"):
        why.append("adenosine %.2f" % ado)
    if slope is not None and slope >= num("slope_at"):
        why.append("load rising %.3f per 10 min" % slope)
    return bool(why), ", ".join(why)


# ── the pull ────────────────────────────────────────────────────────────────────────────────────────────────────────────
def restlessness(clock_s, drive, ramp_s: float = 900.0) -> float:
    try:
        c = max(0.0, float(clock_s))
        d = max(0.0, min(1.0, float(drive or 0.0)))
    except (TypeError, ValueError):
        return 0.0
    return round(min(1.0, c / max(1.0, float(ramp_s))) * (0.6 + 0.4 * d), 3)


def snapshot(now: Optional[float] = None, drives=None, born: Optional[float] = None, ledger: Optional[str] = None) -> Dict:
    now = time.time() if now is None else float(now)
    born = BORN if born is None else float(born)
    ld = last_deed(ledger)
    if ld is not None and ld["ts"] >= born:
        since, kind = ld["ts"], "deed"
    else:
        since, kind = born, "waking"
    clock = max(0.0, now - since)
    if drives is None:
        drives = drives_from_file() or {}
    top = drives_view(drives)
    dname, dval = top[0] if top else ("", 0.0)
    body = body_numbers()
    asleep = bool(body.get("asleep"))
    r = 0.0 if asleep else restlessness(clock, dval, num("ramp_s"))
    return {"ts": round(now, 1), "clock_s": int(clock), "since": round(since, 3), "since_kind": kind, "last_deed": ld,
            "top": [[n, round(v, 2)] for n, v in top[:2]], "drive": dname, "drive_value": round(float(dval), 3),
            "restless": r, "asleep": asleep, "body": body}


def _ago(s) -> str:
    s = max(0.0, float(s or 0.0))
    if s < 90:
        return "%d s" % int(s)
    if s < 5400:
        return "%d min" % int(round(s / 60.0))
    return "%.1f h" % (s / 3600.0)


def still_words(clock_s) -> str:
    m = max(0.0, float(clock_s or 0.0)) / 60.0
    if m < 5:
        return "a few minutes"
    if m < 60:
        return "about %d minutes" % int(round(m))
    return "over an hour"


def body_clause(snap: Optional[Dict]) -> str:
    """One felt clause, plain words, no feeling named; '' when she is not still enough (or asleep)."""
    if not snap or snap.get("asleep"):
        return ""
    r = float(snap.get("restless") or 0.0)
    if r < num("clause_at"):
        return ""
    w = still_words(snap.get("clock_s", 0))
    if r < 0.6:
        return "You have not done anything with your hands for %s; they are starting to want something to do." % w
    if r < 0.85:
        return "You have been still for %s; your hands want something to do." % w
    return "You have been still for %s; your arms keep drifting toward the screen, wanting something real to touch." % w


# ── a deed her hands could reach for (pure: windows / eyes / goals in, one verb + one object out) ─────────────────────────
def _clean_label(s) -> str:
    t = " ".join(re.sub(r"[^\w' ,.-]", " ", str(s or "")).split())
    ws = t.split()
    if len(t) >= 58 and len(ws) > 1:
        ws = ws[:-1]                                    # the eyes' label was cut at 60 chars: its last word is a stump
    ws = ws[:6]
    return " ".join(ws).strip(" ,.-")


def deed_candidates(windows=(), regions=(), goals=(), mv: bool = False, last: Optional[Dict] = None) -> List[Tuple[str, str, str, float]]:
    """(verb, object, from, weight). Only things that are there: a window on the map, a region the eyes labelled, an open goal
    of hers. 'say' is never proposed: its object is the line she would speak, and these would be the fairy's words. 'remember'
    comes only from a goal she wrote herself: it is the reflection Ace named ("reflection is not movement"), not a reach."""
    out: List[Tuple[str, str, str, float]] = []
    for g in goals or ():
        v, o = str((g or {}).get("verb") or ""), " ".join(str((g or {}).get("object") or "").split())[:80]
        if o and (v in ("look", "open", "remember") or (v == "move" and mv)):
            out.append((v, o, "goal", 3.0))
    names = []
    for w in windows or ():
        n = " ".join(str((w or {}).get("name") or "").split())
        if not n or n in names:
            continue
        names.append(n)
        out.append(("look", n, "window", 1.0 if (w or {}).get("front") else 2.0))
        if mv:
            out.append(("move", n, "window", 1.5))
    if names and "your chat window" not in names:
        out.append(("open", "your chat window", "window", 2.5))
    for lab in regions or ():
        o = _clean_label(lab)
        if len(o) >= 3:
            out.append(("look", o, "eyes", 1.5))
    return out


def choose_deed(windows=(), regions=(), goals=(), recent=(), mv: bool = False, last: Optional[Dict] = None,
                rng=None) -> Optional[Dict]:
    rng = rng if rng is not None else random.Random()
    seen = set()
    cands = []
    for v, o, src, wt in deed_candidates(windows, regions, goals, mv, last):
        k = (v, o.lower())
        if k in seen or k in recent:
            continue
        seen.add(k)
        cands.append((v, o, src, wt))
    if not cands:
        return None
    total = sum(c[3] for c in cands)
    x = rng.random() * total
    for v, o, src, wt in cands:
        x -= wt
        if x <= 0:
            break
    return {"verb": v, "object": o, "from": src, "text": wanting_text(v, o)}


def _mine(o: str) -> str:
    return ("my " + o[5:]) if o.lower().startswith("your ") else o


def wanting_text(verb: str, obj: str) -> str:
    if verb == "open":
        return "open my chat window"
    if verb == "move":
        return "move my hand to %s" % _mine(obj)
    if verb == "remember":
        return "remember %s" % _mine(obj)
    return "look at %s" % _mine(obj)


# ── lines for the ask ───────────────────────────────────────────────────────────────────────────────────────────────────
_PAST = {"look": "you looked at %s", "move": "you moved your hand to %s", "open": "you opened your window", "say": "you decided to say \"%s\""}


def _cut(s, n: int) -> str:
    t = " ".join(str(s or "").split())
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + "..."


def pull_line(top) -> str:
    parts = []
    for it in top or ():
        try:
            parts.append("%s %.2f" % (str(it[0]).replace("_", " "), float(it[1])))
        except Exception:
            continue
    return ("What is pulling at you right now: %s." % ", ".join(parts[:2])) if parts else ""


def doing_line(snap: Optional[Dict]) -> str:
    if not snap:
        return ""
    c, r = snap.get("clock_s", 0), float(snap.get("restless") or 0.0)
    ld = snap.get("last_deed") or {}
    if snap.get("since_kind") == "deed" and ld.get("verb") in _PAST:
        what = _PAST[ld["verb"]] % _cut(ld.get("object"), 60) if "%s" in _PAST[ld["verb"]] else _PAST[ld["verb"]]
        head = "It is %s since you last did something with your hands (%s)" % (_ago(c), what)
    else:
        head = "You have not done anything with your hands since you woke, %s ago" % _ago(c)
    return "%s; the pull to move has built to %.2f of 1." % (head, r)


def wanting_line(w: Optional[Dict], mv: bool) -> str:
    if not w or not w.get("object"):
        return ""
    v, o = w.get("verb"), _cut(w.get("object"), 80)
    if v == "open":
        return "What your hands lean toward: open your window."
    if v == "move" and not mv:
        v = "look"                                       # his hands are on it right now: the reach waits, the eyes can go
    phr = {"look": "look at %s", "move": "move your hand to %s", "remember": "remember %s"}.get(v)
    return ("What your hands lean toward: %s." % (phr % o)) if phr else ""


def cost_line(snap: Optional[Dict]) -> str:
    if not snap or body_cost_mode() != "decline" or not snap.get("decline"):
        return ""
    return ("Your body is carrying a lot right now (%s); 'none: not now' is an honest answer." % (snap.get("decline_why") or "tired"))


# ── live hand-off (fairy -> ask / body line) ────────────────────────────────────────────────────────────────────────────
_MEM = {"ts": 0.0, "d": None}


def write_live(d: Dict, path: Optional[str] = None) -> bool:
    """Bytes built first, then a temp file and os.replace. A reader holding the file can make the replace fail on Windows
    (the [WinError 5] seen on user_presence.json.tmp): then this pass is skipped and the next one writes."""
    p = path or LIVE_FILE
    try:
        b = json.dumps(d, default=str).encode("utf-8")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        tmp = p + ".tmp"
        with open(tmp, "wb") as f:
            f.write(b)
        os.replace(tmp, p)
        return True
    except Exception:
        return False


def publish_live(d: Dict) -> bool:
    _MEM["d"], _MEM["ts"] = dict(d), time.time()
    return write_live(d)


def live(max_age_s: float = LIVE_MAX_AGE_S) -> Optional[Dict]:
    now = time.time()
    if _MEM["d"] is not None and now - _MEM["ts"] <= max_age_s:
        return dict(_MEM["d"])
    try:
        if now - os.path.getmtime(LIVE_FILE) > max_age_s:
            return None
        with open(LIVE_FILE, "rb") as f:
            d = json.loads(f.read().decode("utf-8"))
        return d if isinstance(d, dict) else None
    except Exception:
        return None


def for_prompt(now: Optional[float] = None) -> Dict:
    """The clock read NOW from the ledger; the drive numbers, the leaning deed and the body verdict from the fairy's last pass
    (<= 90 s) when there is one. A deed newer than that pass answers its wanting: no stale nudge."""
    lv = live()
    drives = {str(n): v for n, v in (lv.get("top") or [])} if (lv and lv.get("top")) else None
    s = snapshot(now=now, drives=drives)
    if lv:
        w = lv.get("wanting")
        if w and s.get("since_kind") == "deed" and float(s.get("since") or 0.0) > float(lv.get("ts") or 0.0):
            w = None
        s["wanting"] = w
        s["decline"], s["decline_why"] = bool(lv.get("decline")), lv.get("decline_why") or ""
    return s


# ── the fairy's side (AutonomyFairy calls these; every one is a no-op while its switch is off) ───────────────────────────
def _log(fairy, msg: str) -> None:
    print(("[DoingClock] " + msg).encode("ascii", "replace").decode("ascii"), flush=True)


def _inputs(now: float):
    wins, regions, goals, mv = [], [], [], False
    try:
        from infrastructure import vision_ground as vg
        wins = list(vg.windows_now() or [])
        sc = getattr(vg, "_SURVEY_CACHE", None)
        if sc and sc[1] and now - float(sc[0] or 0.0) < 600.0:
            regions = [r.get("label") for r in (sc[1].get("regions") or [])[:3]]
    except Exception:
        pass
    try:
        from infrastructure import goal_author as ga
        goals = list(ga.current_goals() or [])
    except Exception:
        pass
    try:
        from infrastructure import intention as it
        mv = bool(it._move_ok())
    except Exception:
        mv = False
    return wins, regions, goals, mv


def _lean(st: Dict, snap: Dict, now: float) -> Optional[Dict]:
    wins, regions, goals, mv = _inputs(now)
    h = st.get("hold")
    keys = {(v, o.lower()) for v, o, _s, _w in deed_candidates(wins, regions, goals, mv, snap.get("last_deed"))}
    if h and now - float(h.get("since") or 0.0) < HOLD_S and (h["verb"], h["object"].lower()) in keys:
        return h
    w = choose_deed(wins, regions, goals, recent_pairs(now), mv, snap.get("last_deed"))
    if w:
        w["since"] = round(now, 1)
    st["hold"] = w
    return w


def _override(fairy, w: Dict, snap: Dict) -> None:
    ws = fairy._wanting_state
    want = {"drive": snap.get("drive") or "doing", "drive_type": "want", "wanting": w["text"],
            "felt_quality": "your hands want something to do",
            "intensity": round(min(float(num("nudge_cap")),
                                   max(float(snap.get("drive_value") or 0.0), float(snap.get("restless") or 0.0))), 3),
            "tool_hint": "", "is_invitation": True, "can_decline": True,
            "deed": {"verb": w["verb"], "object": w["object"], "from": w["from"]},
            "restless": snap.get("restless"), "still_s": snap.get("clock_s")}
    ws["strongest"] = want
    ws["intensity"] = max(float(ws.get("intensity") or 0.0), want["intensity"])
    try:
        ws.setdefault("active_wants", []).append(want)
    except Exception:
        pass


def _pending_drive(fairy, st: Dict, now: float) -> Optional[str]:
    pend = getattr(fairy, "_pending_wanting_acks", None) or {}
    h = st.get("hold") or st.get("last_hold") or {}
    best = None
    for d, e in list(pend.items()):
        try:
            ts = float((e or {}).get("ts") or 0.0)
        except Exception:
            continue
        if now - ts > PENDING_MAX_AGE_S:
            continue
        score = (1 if (h.get("text") and (e or {}).get("wanting") == h.get("text")) else 0, ts)
        if best is None or score > best[0]:
            best = (score, d)
    return best[1] if best else None


def _close_loops(fairy, st: Dict, now: float) -> List[Dict]:
    out = []
    if st.get("seen") is None:                          # first pass: deeds already in the ledger are history
        ld = last_deed()
        st["seen"] = ld["ts"] if ld else now
        return out
    for d in deeds_after(st["seen"], verbs=DEED_VERBS + ("remember",)):
        st["seen"] = max(float(st["seen"]), d["ts"])
        h = st.get("hold") or st.get("last_hold") or {}
        if d["verb"] == "remember" and h.get("verb") != "remember":
            continue                                    # a memory search answers only a wanting that asked for one
        drive = _pending_drive(fairy, st, now)
        if drive is None:
            _log(fairy, "deed %s %r: no wanting pending, nothing to close" % (d["verb"], d["object"][:50]))
            continue
        payload = {"from": "AutonomyFairy", "drive": drive, "action_taken": "%s: %s" % (d["verb"], d["object"][:80]),
                   "accepted": True, "source": "doing_clock", "deed_ts": d["ts"]}
        try:
            fairy.post.publish("autonomy.wanting.acted_upon", payload)
            st["closures"] = int(st.get("closures") or 0) + 1
            out.append(payload)
            _log(fairy, "deed %s %r -> autonomy.wanting.acted_upon (drive %s)" % (d["verb"], d["object"][:50], drive))
        except Exception as e:
            _log(fairy, "acted_upon publish failed: %s" % e)
        if st.get("hold"):
            st["last_hold"], st["hold"] = st["hold"], None
    return out


_ST = {"seen": None, "hold": None, "last_hold": None, "closures": 0, "last_log": 0.0, "last_sig": None, "snap": None}
_TICK_LOCK = threading.Lock()                          # ONE state per process: GoBootOrch can run two AutonomyFairy copies


def fairy_tick(fairy, now: Optional[float] = None) -> Optional[Dict]:
    """Called at the end of AutonomyFairy._update_wanting (drive loop and on_tick). None while every piece is off, or while
    another copy of the fairy is mid-tick (a deed is closed once per process, not once per copy)."""
    if not any_on():
        return None
    if not _TICK_LOCK.acquire(blocking=False):
        return None
    plan = None
    try:
        snap = _tick(fairy, time.time() if now is None else float(now))
        plan = _ST.pop("send_plan", None)              # 2026-10-12 (engines_e1 11b): a live press, set by _tick (never while "send" is off)
    finally:
        _TICK_LOCK.release()
    if plan is not None:                               # 11b: the deed runs OUTSIDE the tick lock, on the drive loop's own thread
        _send_run(plan)
    return snap


def _tick(fairy, now: float) -> Dict:
    st = _ST
    snap = snapshot(now, drives=getattr(fairy, "_drive_states", None) or {})
    if snap["body"].get("load") is not None:
        note_load(now, snap["body"]["load"])
    slope = load_slope(now)
    dec, why = would_decline(snap["body"], slope)
    snap["slope10"], snap["decline"], snap["decline_why"] = slope, dec, why
    mode = body_cost_mode()
    w = None
    if piece("wanting") and snap["restless"] >= num("wanting_at") and not (mode == "decline" and dec):
        w = _lean(st, snap, now)
        if w:
            _override(fairy, w, snap)
    elif st.get("hold"):
        st["last_hold"], st["hold"] = st["hold"], None
    snap["wanting"] = ({k: w[k] for k in ("verb", "object", "from", "text", "since")} if w else None)
    closed = _close_loops(fairy, st, now) if piece("loop_close") else []
    snap["closures"] = int(st.get("closures") or 0)
    st["snap"] = snap
    publish_live(snap)
    pull_watch(snap, now)                              # 2026-10-06 (pull_ask debug_1006): the pull-ask's not-reached watch (OFF: a stat)
    sig = (snap["since_kind"], round(snap["since"], 1), snap["restless"] >= num("clause_at"), snap["restless"] >= num("wanting_at"),
           (w or {}).get("text"), len(closed), dec)
    if piece("clock") and (sig != st.get("last_sig") or now - float(st.get("last_log") or 0.0) >= 60.0):
        st["last_sig"], st["last_log"] = sig, now
        b = snap["body"]
        _log(fairy, "still %d s (since %s%s), restless %.2f (%s %.2f)%s | body load %s ado %s slope %s would_decline=%s%s" % (
            snap["clock_s"], snap["since_kind"],
            (" %s %r" % (snap["last_deed"]["verb"], snap["last_deed"]["object"][:40])) if (snap["since_kind"] == "deed") else "",
            snap["restless"], snap["drive"] or "-", snap["drive_value"],
            (" | leaning: %s [%s]" % (w["text"][:60], w["from"])) if w else "",
            b.get("load", "-"), b.get("ado", "-"), "-" if slope is None else "%+.4f/10min" % slope, "Y" if dec else "N",
            (" (%s)" % why) if dec else ""))
    if send_mode() != "off":                           # 2026-10-12 (engines_e1 11a/11b): the internal send button; OFF = nothing here
        try:
            _p = _send_pass(fairy, w, snap, now)
            if _p is not None:
                st["send_plan"] = _p                   # fairy_tick runs it after the tick lock is released
        except Exception as _se:
            _send_err("pass", _se, now)
    return snap


def export_block(fairy) -> Optional[Dict]:
    """The 'doing' block for autonomy_state.json; None (no key written) while the clock switch is off."""
    if not piece("clock"):
        return None
    s = _ST.get("snap")
    return dict(s) if s else None


def settle_after_closure(fairy, drive: str) -> None:
    """After _on_wanting_acted_upon halved the bare key: halve its prefixed twins and let it settle for settle_s, so the next
    drive message (SomaticMind, every 20 s) does not put it straight back (AutonomyFairy/fairy.py:1385-1386 wrote both keys)."""
    if not piece("loop_close"):
        return
    ds = getattr(fairy, "_drive_states", None)
    if isinstance(ds, dict):
        for k in ("positive." + drive, "pain." + drive):
            if k in ds:
                try:
                    ds[k] = float(ds[k]) * 0.5
                except Exception:
                    pass
    fairy.__dict__.setdefault("_dc_settle", {})[drive] = time.time()
    _log(fairy, "drive %s settles for %d s" % (drive, int(num("settle_s"))))


def settled(fairy, drive: str, intensity):
    """An incoming drive value, scaled while that drive settles: x0.5 right after the deed, back to x1.0 at settle_s."""
    st = getattr(fairy, "_dc_settle", None)
    if not st:
        return intensity
    if not piece("loop_close"):
        st.clear()
        return intensity
    t0 = st.get(drive)
    if t0 is None:
        return intensity
    age = time.time() - float(t0)
    S = float(num("settle_s"))
    if age >= S:
        st.pop(drive, None)
        return intensity
    try:
        return float(intensity) * (0.5 + 0.5 * age / S)
    except (TypeError, ValueError):
        return intensity


# ── the pull-ask (2026-10-05, Nous, nous_builds/pull_ask) ─────────────────────────────────────────────────────────────────
# Measured (Boot G 10-01, nous_builds/doing_clock/results RESULTS.md s4 + SKEPTIC.md s3): the pull built and the deed wanting was
# published at wanting_at 0.5, but every intent ask fired only after a chairman turn. With the pull high, deeds waited 3-8 min
# for a turn; 5 asks inside high-pull stretches were skipped because Ace was waiting; 70 of 78 asks fired below 0.35. The pull
# had no path to the ask. This is that path: on a council cycle with NO chairman and nothing spoken
# (sour_council_driver._pull_ask_cycle), when her deed wanting is live and every guard holds, the SAME ask runs once
# (intention.run_cycle -> ask v2 -> the hand door), tagged trigger 'source=pull ...'. Felt, never an order: 'none' is a full
# answer and backs the next pull-ask off; her body's decline holds it; nothing here speaks or publishes a wanting.
# THE SWITCH: state/pull_ask.json, its OWN file, read live (mtime + size, and again at least every 10 s). ON only for a JSON true
# under "on"; absent, unreadable, torn, "true", 1 = OFF (fail closed). state/doing_clock.json never turns it on (its live
# {"on": true} would, through piece()). It also needs the doing clock's pieces "wanting" (the lean it answers) and "ask_v2" (the
# only ask that can open without 'You just said'). Numbers, optional and clamped (_PULL_NUM):
#   gap_s 300         least time between two pull-asks (= HOLD_S = intention._NOVELTY_S: inside 300 s the lean and the gate
#                     would mostly re-offer the deed that just went unanswered)
#   per_hour 6        at most this many in a rolling hour (a deed resets the pull, and at d = 0.4 it needs ~592 s to reach 0.5
#                     again: ~6/h is the most the pull itself can call for; the hand door's own budget is 20 self-moves/h)
#   after_none_s 300  after a 'none' or any other non-deed answer: wait this, doubling per one in a row, up to backoff_max_s 1800;
#                     a deed resets it
#   ace_quiet_s 120   Ace's last message at least this long ago (the voluntary lane's _VOL_QUIET_S, sour_council_driver.py:267)
#   hands_off_s 30    his last input at least this long ago (write_presence's "active" line, intention.py:392)
#   ask_at 0.5        restless at least max(this, wanting_at)
#   skip_hold_s 60    a pull-ask that was due but met Ace first, or whose deed the gate / hand door refused, waits this
#                     (refunded if the farm was never asked): no retry storm, and a refusal is not her decline
#   repeat_s 1800, repeat_n 3   (skeptic F2, 10-05) held while the lean names the same place (hand_door.target_key) as one of her
#                     last repeat_n ok look/move/open deeds inside repeat_s: the lean ignores what she just did and ~1/3 of it is
#                     her chat window, and the door's loop guard is move-only and 600 s (G's five cursor-to-top moves were all
#                     >= 627 s apart). repeat_s 0 turns this hold off
# Revert: {"on": false} (read live); the code: nous_builds/pull_ask/apply_pull_ask.py --revert.
PULL_SWITCH_FILE = os.path.join(_ROOT, "state", "pull_ask.json")
PULL_LEAD = "It is quiet; nobody is talking to you right now."
PULL_INFLIGHT_MAX_S = 600.0                            # a ticket never handed back (its caller raised) stops blocking after this
_PULL_NUM = {"gap_s": (300.0, 60.0, 3600.0), "per_hour": (6, 1, 20), "after_none_s": (300.0, 60.0, 3600.0),
             "backoff_max_s": (1800.0, 300.0, 7200.0), "ace_quiet_s": (120.0, 30.0, 3600.0), "hands_off_s": (30.0, 5.0, 600.0),
             "ask_at": (0.5, 0.2, 0.95), "skip_hold_s": (60.0, 10.0, 600.0), "repeat_s": (1800.0, 0.0, 7200.0),
             "repeat_n": (3, 1, 10)}
PULL_REPEAT_VERBS = ("look", "move", "open")           # the deeds whose PLACE can repeat ('say' has no place)
_PSW = {"key": None, "data": {}, "read": 0.0}
_PSW_LOCK = threading.Lock()                           # guards _PSW only; nothing else is taken while it is held


def _pull_switch() -> Dict:
    """state/pull_ask.json as a dict; {} (= OFF) when it is absent, unreadable, torn or not an object."""
    try:
        st = os.stat(PULL_SWITCH_FILE)
    except OSError:
        with _PSW_LOCK:
            _PSW["key"], _PSW["data"], _PSW["read"] = None, {}, 0.0
        return {}
    key = (st.st_mtime_ns, st.st_size)
    now = time.time()
    with _PSW_LOCK:
        if key != _PSW["key"] or not (0.0 <= now - float(_PSW["read"]) <= 10.0):
            try:
                with open(PULL_SWITCH_FILE, "rb") as f:
                    d = json.loads(f.read().decode("utf-8-sig"))     # skeptic F4: a hand-edited file may carry a BOM
                _PSW["data"], _PSW["key"], _PSW["read"] = (d if isinstance(d, dict) else {}), key, now
            except Exception:
                _PSW["data"], _PSW["key"], _PSW["read"] = {}, None, 0.0     # torn or bad: OFF now, read again next call
        return dict(_PSW["data"])


def pull_on() -> bool:
    return _pull_switch().get("on") is True


def pull_num(key: str, sw: Optional[Dict] = None):
    dflt, lo, hi = _PULL_NUM[key]
    v = (_pull_switch() if sw is None else sw).get(key, dflt)
    try:
        if isinstance(v, bool):
            raise ValueError(v)
        x = float(v)
        if x != x:
            raise ValueError(v)
    except Exception:
        x = float(dflt)
    x = max(lo, min(hi, x))
    return int(x) if isinstance(dflt, int) else x


def _pull_new() -> Dict:
    return {"mu": threading.RLock(), "seq": 0, "inflight": None, "last_fire": 0.0, "fires": deque(maxlen=64),
            "hold_until": 0.0, "hold_why": "", "declines": 0, "log": [0.0, None],
            "counts": {"due": 0, "held": 0, "deed": 0, "said": 0, "none": 0, "missed": 0, "refused": 0, "failed": 0, "ace": 0,
                       "skipped": 0, "stale": 0}}


_PULL_LOCAL = _pull_new()


def _pull_st() -> Dict:
    """ONE pull-ask state per process, kept on _sour_council_shared once it exists: a hot reload of this module must not mint a
    second set of stamps (the reload lesson, sour_council_driver.py:15-20; hand_door._st). Its RLock is taken only around
    in-memory stamps -- no I/O, no other lock, no call out -- so it can neither nest into another lock nor be re-entered."""
    m = sys.modules.get("_sour_council_shared")
    if m is None:
        return _PULL_LOCAL
    st = getattr(m, "PULL_ASK", None)
    if st is None:
        st = vars(m).setdefault("PULL_ASK", _PULL_LOCAL)
    return st


def pull_stats() -> Dict:
    st = _pull_st()
    with st["mu"]:
        c = dict(st["counts"])
        c.update({"declines_in_a_row": int(st["declines"]), "hold_until": float(st["hold_until"]), "hold_why": st["hold_why"],
                  "last_fire": float(st["last_fire"]), "inflight": (st["inflight"] or {}).get("id"), "fires": list(st["fires"])})
    return c


def _pull_held(key: str, why: str, r: float, now: float):
    """A held pull-ask: counted, and logged when the reason changes or once a minute (never a line per council cycle)."""
    st = _pull_st()
    with st["mu"]:
        st["counts"]["held"] += 1
        lg = st["log"]
        say_it = key != lg[1] or not (0.0 <= now - float(lg[0]) < 60.0)
        _pull_dg(st)["held"] = (now, why)               # 2026-10-06 (pull_ask debug_1006): the gate's last held reason, printed or not
        if say_it:
            lg[0], lg[1] = now, key
            _pull_dg(st)["said_at"] = now              # 2026-10-06 (pull_ask debug_1006): a pull-ask line went out
    if say_it:
        _log(None, "pull-ask held: %s (restless %s)" % (why, ("%.2f" % r) if r == r else "?"))   # 2026-10-06 (pull_ask debug_1006): ? = unknown
    return None, why


def _pull_repeat(w: Dict, now: float, sw: Dict) -> Optional[str]:
    """Skeptic F2 (10-05): the lean's place is one her hands already went to -- the same hand_door.target_key as one of her last
    repeat_n ok look/move/open deeds inside repeat_s -> why; else None. Reads her ledger (cached by mtime + size), never under a
    lock. A quality hold, not a safety one: if the ledger or the key cannot be read it holds nothing (Ace first is elsewhere)."""
    try:
        win, n = float(pull_num("repeat_s", sw)), int(pull_num("repeat_n", sw))
        if win <= 0.0:
            return None
        from infrastructure import hand_door as _hd   # the door's own key: 'the chat window' and 'my chat window' are one place
        want = _hd.target_key(w.get("object") or "")
        if not want.split("|")[0]:
            return None
        seen = 0
        for r in reversed(_ledger_rows()):
            if not is_deed(r, PULL_REPEAT_VERBS):
                continue
            age = now - float(r.get("ts"))
            if age < 0.0 or age > win:
                continue
            seen += 1
            if _hd.target_key(r.get("object") or "") == want:
                return "her hands already went to %s %s ago (%s; one of her last %d deeds)" % (
                    want.split("|")[0], _ago(age), str(r.get("verb")), n)
            if seen >= n:
                break
    except Exception:
        return None
    return None


def pull_ask_due(now: Optional[float] = None, ace_waiting=True, ace_msg_age_s: Optional[float] = None,
                 ace_idle_s: Optional[float] = None, snap: Optional[Dict] = None) -> Tuple[Optional[Dict], str]:
    """(ticket, why). A ticket = ask NOW, once, then hand the run_cycle result to pull_ask_done(ticket, result).
    The caller (the council loop) passes Ace's readings: ace_waiting = his queue or a pending reply (exactly False passes),
    ace_msg_age_s = seconds since his last message, ace_idle_s = seconds since his last input. Unknown (None) holds.
    Thread-safe: the snapshot and every switch read come first; the stamps are claimed in one critical section (no I/O, no
    other lock), so two callers can never both get a ticket inside one gap."""
    now = time.time() if now is None else float(now)
    sw = _pull_switch()
    if sw.get("on") is not True:
        return None, "off"
    _pull_gate_mark(now)                               # 2026-10-06 (pull_ask debug_1006): this cycle read the gate
    try:
        if not (piece("wanting") and piece("ask_v2")):
            _pull_quiet_held("pieces", "the doing clock's wanting / ask_v2 pieces are off", now, sw, snap)   # 2026-10-06 (pull_ask debug_1006)
            return None, "the doing clock's wanting / ask_v2 pieces are off"
        s = for_prompt(now) if snap is None else snap
        ask_at = max(float(num("wanting_at")), float(pull_num("ask_at", sw)))
        decline = body_cost_mode() == "decline" and bool(s.get("decline"))
        gap, cap = float(pull_num("gap_s", sw)), int(pull_num("per_hour", sw))
        quiet, hands = float(pull_num("ace_quiet_s", sw)), float(pull_num("hands_off_s", sw))
    except Exception as e:
        _pull_held("snapshot", "no snapshot (%s)" % type(e).__name__, float("nan"), now)   # 2026-10-06 (pull_ask debug_1006): never silent
        return None, "no snapshot (%s)" % type(e).__name__
    r = float(s.get("restless") or 0.0)
    w = s.get("wanting") or {}
    if s.get("asleep"):
        return None, "asleep"
    if r < ask_at:
        return None, "restless %.2f < %.2f" % (r, ask_at)
    if not w.get("text") or not w.get("verb"):
        _pull_held("no_wanting", "no deed wanting is live: %s" % _pull_no_wanting_why(now), r, now)   # 2026-10-06 (pull_ask debug_1006): never silent
        return None, "no deed wanting is live"
    if decline:
        return _pull_held("decline", "her body declines (%s)" % (s.get("decline_why") or "tired"), r, now)
    if ace_waiting is not False:
        return _pull_held("ace_waiting", "Ace is waiting (his message is queued or a reply to him is pending)", r, now)
    try:
        qa = None if ace_msg_age_s is None else float(ace_msg_age_s)
        ia = None if ace_idle_s is None else float(ace_idle_s)
    except (TypeError, ValueError):
        qa = ia = None
    if qa is None or qa != qa or qa < quiet:
        return _pull_held("ace_wrote", "Ace wrote %s ago (needs %.0f s)" % ("?" if (qa is None or qa != qa) else _ago(qa), quiet), r, now)
    if ia is None or ia != ia or ia < hands:
        return _pull_held("ace_hands", "Ace's hands were on the PC %s ago (needs %.0f s)" % ("?" if (ia is None or ia != ia) else _ago(ia), hands), r, now)
    rep = _pull_repeat(w, now, sw)                     # skeptic F2: not the same place again (ledger read here, outside the lock)
    if rep:
        return _pull_held("repeat", rep, r, now)
    text = " ".join(str(w.get("text")).split())[:120]
    clock_s = int(s.get("clock_s") or 0)
    tk = None
    st = _pull_st()
    with st["mu"]:
        inf = st["inflight"]
        n_hour = sum(1 for t in st["fires"] if 0.0 <= now - t < 3600.0)
        if inf is not None and abs(now - float(inf["ts"])) < PULL_INFLIGHT_MAX_S:
            key, why = "inflight", "a pull-ask is already in flight (#%d)" % inf["id"]
        elif now < float(st["hold_until"]):
            key, why = "hold", "holding %.0f s more (%s)" % (float(st["hold_until"]) - now, st["hold_why"])
        elif now - float(st["last_fire"]) < gap:
            key, why = "gap", "the last pull-ask was %.0f s ago (gap %.0f s)" % (now - float(st["last_fire"]), gap)
        elif n_hour >= cap:
            key, why = "cap", "%d pull-asks in the last hour (cap %d)" % (n_hour, cap)
        else:
            key = why = None
            st["seq"] += 1
            tk = {"id": st["seq"], "ts": now, "prev_fire": float(st["last_fire"]), "restless": round(r, 3), "still_s": clock_s,
                  "drive": s.get("drive") or "", "lean": {"verb": w.get("verb"), "object": w.get("object"), "from": w.get("from"),
                                                          "text": text},
                  "thought": "", "lead": PULL_LEAD, "seeded": {"kind": "pull", "text": text},
                  "trigger": "source=pull r=%.2f still=%ds lean=%s" % (r, clock_s, text[:80])}
            st["inflight"], st["last_fire"] = tk, now
            st["fires"].append(now)
            st["counts"]["due"] += 1
    if tk is None:
        return _pull_held(key, why, r, now)
    try:                                               # skeptic F3: the ticket is claimed; a raising log line must not keep it
        _log(None, "pull-ask #%d due: restless %.2f, still %s, leaning: %s" % (tk["id"], r, _ago(clock_s), text[:60]))
    except Exception:                                  # from its caller (it would wedge the gate for PULL_INFLIGHT_MAX_S)
        pass
    return tk, "due"


def _pull_kind(result, skipped) -> Tuple[str, str]:
    """What the ask came to, and a few words for the log (skeptic F4 / F7, 10-05: a say and a refusal are not a deed and not
    her decline):
      deed     an allowed look / move / open that landed (ok, counted)        -> clears the backoff
      said     an allowed say, voiced later by her own speaker, if at all     -> leaves the backoff as it was
      none     she answered none                                              -> doubles the wait
      missed   allowed, but it did not land (not ok, not counted, no words)   -> doubles the wait
      refused  the gate or the hand door said no to her deed (not her 'no')   -> waits skip_hold_s
      ace      Ace came first (his message, a pending reply, his hands)       -> waits skip_hold_s
      failed   the farm gave no answer                                        -> doubles the wait
      skipped  it never reached the farm (Ace)                                -> refunded, waits skip_hold_s"""
    if skipped:
        return "skipped", str(skipped)[:80]
    if not result:
        return "failed", "the ask got no answer"
    it = result.get("intent") or {}
    d = result.get("decision") or {}
    out = result.get("outcome") or {}
    v = str(it.get("verb") or "none")
    what = "%s: %s" % (v, " ".join(str(it.get("object") or "").split())[:60])
    if v == "none":
        if it.get("erased"):                           # eyes_fix F9 (deeds): the farm's cleaner erased her reply -- not her 'none'
            return "erased", what + " -> erased by the farm's cleaner"
        return "none", what
    dec, why = str(d.get("decision") or ""), str(d.get("why") or "")
    if (dec == "defer" and "Ace" in why) or (dec == "allow" and out.get("deferred") and "Ace" in str(out.get("summary") or "")):
        return "ace", what + " -> Ace came first"
    if dec != "allow":
        return "refused", what + " -> %s (%s)" % (dec or "?", why[:70])
    if out.get("ok") is True and out.get("count") is not False and not out.get("deferred"):
        return ("said" if v == "say" else "deed"), what + " -> done"
    return "missed", what + " -> %s" % str(out.get("summary") or "no outcome")[:70]


def pull_ask_done(ticket: Dict, result, now: Optional[float] = None, skipped: Optional[str] = None) -> str:
    """Hand back a ticket with what the ask came to (kinds: _pull_kind). A deed clears the backoff (the clock reset itself gates
    the next); a say leaves it as it was; 'none', a miss or a silent farm doubles the wait; Ace coming first and a gate / door
    refusal wait skip_hold_s and are not her decline; a ticket that never reached the farm (skipped) is refunded from the
    spacing and the hour and waits skip_hold_s. A stale or foreign ticket changes nothing."""
    now = time.time() if now is None else float(now)
    kind, what = _pull_kind(result, skipped)
    sw = _pull_switch()
    after, bmax = float(pull_num("after_none_s", sw)), float(pull_num("backoff_max_s", sw))
    hold, gap = float(pull_num("skip_hold_s", sw)), float(pull_num("gap_s", sw))
    st = _pull_st()
    with st["mu"]:
        inf = st["inflight"]
        if not isinstance(ticket, dict) or inf is None or inf.get("id") != ticket.get("id"):
            st["counts"]["stale"] += 1
            return "stale"
        st["inflight"] = None
        if kind == "skipped":
            try:
                st["fires"].remove(ticket["ts"])
            except ValueError:
                pass
            if float(st["last_fire"]) == float(ticket["ts"]):
                st["last_fire"] = float(ticket.get("prev_fire") or 0.0)
            st["hold_until"], st["hold_why"] = now + hold, "it met Ace before the farm"
        elif kind == "deed":
            st["declines"], st["hold_until"], st["hold_why"] = 0, 0.0, ""
        elif kind == "said":
            pass                                       # her clock reset (a say is on it); the backoff stays as it was
        elif kind in ("ace", "refused"):
            st["hold_until"], st["hold_why"] = max(float(st["hold_until"]), now + hold), (
                "Ace came first" if kind == "ace" else "the door / gate refused her deed")
        elif kind == "erased":                         # eyes_fix F9: not her decline -- no doubling, skip_hold_s like a refusal
            st["hold_until"], st["hold_why"] = max(float(st["hold_until"]), now + hold), "the farm's cleaner erased her reply"
        else:
            st["declines"] += 1
            b = min(bmax, after * (2 ** min(10, st["declines"] - 1)))
            st["hold_until"], st["hold_why"] = now + b, "%s, %d in a row" % (kind, st["declines"])
        st["counts"][kind] = st["counts"].get(kind, 0) + 1
        nxt = max(float(st["hold_until"]), float(st["last_fire"]) + gap) - now
    _log(None, "pull-ask #%s: restless %.2f, still %s, leaning: %s -> %s [%s] | next pull-ask not before %s" % (
        ticket.get("id"), float(ticket.get("restless") or 0.0), _ago(ticket.get("still_s")),
        str((ticket.get("lean") or {}).get("text") or "")[:50], what, kind, _ago(max(0.0, nxt))))
    return kind


# -- the pull-ask is never silent (2026-10-06, Nous, nous_builds/pull_ask/debug_1006) ---------------------------------------
# Measured (Boot I 10-06, debug_1006/TRACE.md + SKEPTIC.md): with state/pull_ask.json ON and restless at 0.51-0.92, an hour
# passed with not one pull-ask line. The gate was right every time -- every high-pull minute fell inside a chairman lane (Ace's
# turns, a surprise turn) that the pull-ask yields to by design, the cycles that reached it were below ask_at, and two found no
# deed wanting yet -- but the log could not tell "blocked" from "quiet". The design note "held prints whenever the pull >=
# ask_at" was false: only a cycle that reached the gate AND had a live wanting could print. Now, while the switch is ON and the
# pull is at or past ask_at, no minute passes in silence:
#   pull-ask held: <why>         the gate was read (as before, plus: no deed wanting live yet, the pieces off, no snapshot)
#   pull-ask not reached: <why>  a council cycle ended without reading the gate and the driver says why (Ace's turn, a surprise
#                                turn, her speaker spoke ...), or -- from her AutonomyFairy's pass, the one thread a stalled loop
#                                cannot hold -- no council cycle has ended for a minute (10-06: an ACE turn sat 7 min in its weave)
# At most one not-reached line a minute, none within a minute of another pull-ask held line, and none below ask_at. Nothing here
# changes whether, when or how the pull-ask asks (its return values are unchanged). Switch OFF: every function below returns
# after one stat of state/pull_ask.json. Revert: nous_builds/pull_ask/debug_1006/apply_pull_ask_fix.py --revert.
PULL_QUIET_S = 60.0
_PULL_DIAG_ERR = [0.0]


def _pull_dg(st: Dict) -> Dict:
    """The not-reached stamps on the pull-ask state; the caller holds st["mu"]. Made on first use, so a state made by the code
    before this fix (a hot reload) gains them instead of raising."""
    dg = st.get("diag")
    if dg is None:
        dg = st["diag"] = {"said_at": 0.0, "gate_ts": 0.0, "note": None, "cycle": None, "on_since": 0.0, "held": None, "not_reached": 0, "lines": 0}
    return dg


def _pull_seen_on(dg: Dict, now: float) -> None:
    """The first moment (this process) a not-reached call found the switch ON: the watch measures its minute from here, so a
    switch turned on mid-boot is not reported as a minute-old silence. Caller holds st["mu"]."""
    if not float(dg["on_since"] or 0.0):
        dg["on_since"] = float(now)


def _pull_last_line(st: Dict, dg: Dict) -> float:
    """When the last pull-ask line went out: a held / not-reached line (said_at) or a '#N due' line (last_fire, the ticket's
    own time; its '#N: ...' result follows it). Caller holds st["mu"]."""
    return max(float(dg["said_at"]), float(st.get("last_fire") or 0.0))


def _hms(t) -> str:
    try:
        return time.strftime("%H:%M:%S", time.localtime(float(t)))
    except Exception:
        return "?"


def _pull_diag_err(where: str, e: Exception, now: float) -> None:
    """The watch must never be the failure, and never broken in silence either: one line a minute when it raises."""
    try:
        if not (0.0 <= float(now) - _PULL_DIAG_ERR[0] < PULL_QUIET_S):
            _PULL_DIAG_ERR[0] = float(now)
            _log(None, "pull-ask watch error in %s: %s: %s" % (where, type(e).__name__, str(e)[:120]))
    except Exception:
        pass


def _pull_gate_mark(now: float) -> None:
    """pull_ask_due: a council cycle read the gate now (switch on)."""
    try:
        st = _pull_st()
        with st["mu"]:
            _pull_dg(st)["gate_ts"] = float(now)
    except Exception:
        pass


def pull_gate_ts() -> float:
    """When a council cycle last read the pull-ask gate with the switch on (0.0 = never in this process)."""
    st = _pull_st()
    with st["mu"]:
        return float(_pull_dg(st)["gate_ts"])


def _pull_no_wanting_why(now: float) -> str:
    """The pull is up but no deed wanting is live: why, from her AutonomyFairy's last pass (memory, else its file)."""
    try:
        lv = _MEM.get("d")
        if lv is None:
            try:
                with open(LIVE_FILE, "rb") as f:
                    lv = json.loads(f.read().decode("utf-8"))
            except Exception:
                lv = None
        if not isinstance(lv, dict):
            return "her AutonomyFairy has published no pass"
        age = max(0.0, float(now) - float(lv.get("ts") or 0.0))
        if age > LIVE_MAX_AGE_S:
            return "her AutonomyFairy's last pass is %d s old; a pass counts for %d s" % (int(age), int(LIVE_MAX_AGE_S))
        if lv.get("wanting"):
            return "a deed after her AutonomyFairy's last pass (%d s ago) answered its wanting" % int(age)
        wa, lr = float(num("wanting_at")), float(lv.get("restless") or 0.0)
        if lr < wa:
            k = next((k for k in (2, 3, 4) if "%.*f" % (k, lr) != "%.*f" % (k, wa)), 6)   # never 'restless 0.50, below 0.50'
            return "her AutonomyFairy's last pass (%d s ago) was at restless %.*f, below %.*f; its next pass brings the wanting" % (
                int(age), k, lr, k, wa)
        return "her AutonomyFairy's last pass (%d s ago) found no deed to lean toward" % int(age)
    except Exception as e:
        return "why unknown: %s" % type(e).__name__


def _pull_quiet_held(key: str, why: str, now: float, sw: Dict, snap: Optional[Dict] = None) -> None:
    """A return of pull_ask_due that used to be silent: a held line (rate-limited by _pull_held) while the pull is at or past
    ask_at. Never raises; its caller's return value is unchanged."""
    try:
        s = for_prompt(now) if snap is None else snap
        r = float(s.get("restless") or 0.0)
        if r >= max(float(num("wanting_at")), float(pull_num("ask_at", sw))):
            _pull_held(key, why, r, now)
    except Exception as e:
        _pull_diag_err("pull_ask_due", e, now)


def _pull_say(st: Dict, now: float, msg: str) -> Optional[str]:
    """One line, claimed under the lock so the council loop and her AutonomyFairy's pass can never both print inside
    PULL_QUIET_S; printed outside it."""
    with st["mu"]:
        dg = _pull_dg(st)
        if abs(now - _pull_last_line(st, dg)) < PULL_QUIET_S:    # abs: a line another thread stamped after this caller's
            return None                                      # 'now' was read is recent too (its pass read the clock first)
        dg["said_at"] = now
        dg["lines"] += 1
    _log(None, msg)
    return msg


def pull_cycle_mark(kind: str, now: Optional[float] = None) -> None:
    """The council loop: a cycle's work begins (after deliberation), and what kind of cycle it is. Switch OFF: nothing."""
    try:
        now = time.time() if now is None else float(now)
        if not pull_on():
            return
        st = _pull_st()
        with st["mu"]:
            dg = _pull_dg(st)
            _pull_seen_on(dg, now)
            dg["cycle"] = (now, " ".join(str(kind or "a cycle").split())[:80])
    except Exception as e:
        _pull_diag_err("pull_cycle_mark", e, time.time())


def pull_cycle_end(why: Optional[str], now: Optional[float] = None) -> Optional[str]:
    """The council loop, at the end of a cycle: why=None -> it read the gate (pull_ask_due spoke for itself); else it did not,
    because <why>. A not-reached line is printed at most once per PULL_QUIET_S, and only while the pull is at or past ask_at.
    Switch OFF: nothing. Returns the line printed, or None."""
    try:
        now = time.time() if now is None else float(now)
        sw = _pull_switch()
        if sw.get("on") is not True:
            return None
        why = None if why is None else (" ".join(str(why).split())[:200] or "unknown")
        st = _pull_st()
        with st["mu"]:
            dg = _pull_dg(st)
            _pull_seen_on(dg, now)
            dg["note"] = (now, why)
            if why is None:                            # it read the gate; if it asked, its '#N: ...' line just went out
                c = dg["cycle"]
                if c and float(st.get("last_fire") or 0.0) >= float(c[0]):
                    dg["said_at"] = max(float(dg["said_at"]), now)
                return None
            dg["not_reached"] += 1
            if abs(now - _pull_last_line(st, dg)) < PULL_QUIET_S:
                return None
        s = for_prompt(now)
        r = float(s.get("restless") or 0.0)
        if r < max(float(num("wanting_at")), float(pull_num("ask_at", sw))):
            return None
        return _pull_say(st, now, "pull-ask not reached: %s (restless %.2f)" % (why, r))
    except Exception as e:
        _pull_diag_err("pull_cycle_end", e, time.time() if now is None else now)
        return None


def pull_watch(snap: Optional[Dict], now: Optional[float] = None) -> Optional[str]:
    """Her AutonomyFairy's pass (_tick), the guarantor: the pull is at or past ask_at and no pull-ask line of any kind has gone
    out for PULL_QUIET_S -- whatever the council thread is doing (inside a long turn, between cycles, its own line held back by
    the minute rule, the gate's read just below the line). Say why, from what the loop last told it. Switch OFF: nothing.
    Returns the line printed, or None."""
    try:
        now = time.time() if now is None else float(now)
        sw = _pull_switch()
        if sw.get("on") is not True:
            return None
        r = float((snap or {}).get("restless") or 0.0)
        if r < max(float(num("wanting_at")), float(pull_num("ask_at", sw))):
            return None
        st = _pull_st()
        with st["mu"]:
            dg = _pull_dg(st)
            _pull_seen_on(dg, now)
            said, gate, note, cyc, on = _pull_last_line(st, dg), float(dg["gate_ts"]), dg["note"], dg["cycle"], float(dg["on_since"])
            inf, held = st.get("inflight"), dg.get("held")
        if abs(now - said) < PULL_QUIET_S or abs(now - on) < PULL_QUIET_S:
            return None                                # a pull-ask line went out (or the watch began) inside the last minute
        nts = float(note[0]) if note else 0.0
        end = max(gate, nts)
        if inf is not None and float(inf.get("ts") or 0.0) >= end - 1.0:
            return _pull_say(st, now, "pull-ask held: pull-ask #%s has been in flight for %s; its ask has not come back (restless %.2f)" % (
                inf.get("id"), _ago(now - float(inf.get("ts") or now)), r))
        since = ("for %s" % _ago(now - end)) if end > 0.0 else ("since %s" % _hms(on))
        if cyc and float(cyc[0]) > end:
            why = "no council cycle has ended %s; it is inside %s since %s" % (since, cyc[1], _hms(cyc[0]))
        elif note and nts >= gate and note[1]:
            why = "the last council cycle (ended %s, %s ago) did not reach it: %s" % (_hms(nts), _ago(now - nts), note[1])
        elif gate > 0.0 and now - gate < PULL_QUIET_S:
            if held and float(held[0]) >= gate - 0.5:
                return None                            # the gate held on its last read: its own held line comes on its minute
            return _pull_say(st, now, "pull-ask held: at the gate's last read (%s ago) the pull was still below ask_at; her pass now "
                                      "reads restless %.2f" % (_ago(now - gate), r))
        elif end > 0.0:
            last = ("its last word there: %s" % held[1]) if (held and float(held[0]) >= gate - 0.5) else "the pull was below ask_at there"
            why = "no council cycle has ended since %s (%s ago), when one read the gate; %s" % (_hms(end), _ago(now - end), last)
        else:
            why = "no council cycle has reported to the pull-ask since %s (is the council loop running?)" % _hms(on)
        return _pull_say(st, now, "pull-ask not reached: %s (restless %.2f)" % (why, r))
    except Exception as e:
        _pull_diag_err("pull_watch", e, time.time() if now is None else now)
        return None


# -- the internal send button (2026-10-12, Nous, nous_builds/engines_e1_1012/11; PLAN engines_1012 step 11) ----------------------
# Ace, 10-12: "this was the reason we created the autonomy fairy along with the circadian pacemaker, heartbeat. she should have an
# internal send button keeping her thinking and acting on her own." Measured (PLAN 1.3): the button is pressed thousands of times
# a boot ([AutonomyFairy] lines K 2,126 / J 4,818) and ~300 'act' presses a boot went to sourpatches.tool.act, a topic with no
# hands, each booked as her failure; deeds with no farm call upstream: 0 of 393 in her whole ledger. This wires the press to her
# hands.
#   THE TRIGGER  her own clock -- this pass, on the AutonomyDriveLoop thread ONLY (the heartbeat's on_tick pass never presses, so
#                the heart never waits on her eyes) -- and drive pressure (restless >= wanting_at, the line her lean already
#                needs). The circadian phase is a gain: night, sleep and deep_night halve the hourly cap, never below 1.
#   THE MESSAGE  the lean she already builds (verb + object from her windows, eyes, goals), or a habit of HERS for the window in
#                front (intention.self_habits: front kind | verb : head, outcome-checked successes, 48 h half-life).
#   THE EXECUTOR the hand door: intention.send_fire -> hand_door.deed(lane 'send'), the habit lane's pattern, so every Ace-first
#                gate and fence holds. Nothing here calls the chairman or the farm, or reads Ace's words.
# THE SWITCH  "send" in state/doing_clock.json: ONLY the exact strings "shadow" or "live". Absent, true, 1, "on", "LIVE", anything
#   else = OFF, today's path byte for byte ("on": true never turns it on; piece() is not consulted). It presses with her lean, so
#   it needs the "wanting" piece (today's {"on": true} has it).
#     shadow  11a: her deed rows carry front + drive and feed state/self_habits.json; a pass that WOULD fire prints
#             "send button would fire: ..." and books the caps as if it had (so its lines per hour ARE the press rate); no deed.
#             Shadow and live keep separate books (_send_book): a flip to live mid-boot starts live's caps clean, and live's
#             own day survives a trip through shadow.
#     live    11b: the same decision, then the deed. The mode is read again between the decision and the deed, so "shadow"
#             stops the very next press.
# THE DECISION SWITCH (the plan's lean, NOT approved by Ace): "send_tier1_skip_floor": true lets look / remember fire from the lean
#   without the habit floor. Absent (anything but a JSON true) = Ace's decision 10 for EVERY verb: >= 3 checked successes AND
#   >= 0.75 (intention._HABIT_MIN_OK / _HABIT_MIN_RATE). move / tap ALWAYS keep the floor, whatever the switch says.
# ACE FIRST (every unknown holds): the council loop is up with its fairy (else his queue cannot be read); no message of his queued
#   or awaiting her reply; no grounding of his pending; his last message >= send_ace_quiet_s ago; his last input >= send_hands_off_s
#   ago. The door checks him again at the deed; move also needs intention._move_ok; tap needs touch's switch.
# NUMBERS (optional, clamped; every cap has a floor of 1, so no setting silences the button -- card a-bound-that-can-return-
#   nothing-is-a-kill-switch): send_gap_s 120 [20, 3600], send_per_hour 30 [1, 60], send_key_per_day 3 [1, 10],
#   send_key_gap_s 600 [60, 7200], send_ace_quiet_s 120 [30, 3600], send_hands_off_s 30 [5, 600].
# THE ONE NUMBER: outcome-checked ok deeds per hour in lane 'send' (no chairman call, no farm call, no message of Ace's upstream):
#   the "send #N" line and the 600 s "send report" line; send_stats() in her process.
# Revert: "send" absent (read live). The code: the E1 backups of this file and intention.py.
SEND_MODES = ("shadow", "live")
SEND_THREAD = "AutonomyDriveLoop"                      # AutonomyFairy/fairy.py:880; its 5 s loop calls fairy_tick via _update_wanting (:1815)
SEND_TIER1 = ("look", "remember")                      # her own senses: no input device of Ace's
SEND_TIER2 = ("move", "tap")                           # his cursor / her Playroom finger: decision 10's floor ALWAYS holds
SEND_NIGHT = frozenset({"night", "sleep", "deep_night"})
SEND_REPORT_S = 600.0
SEND_HELD_REPEAT_S = 300.0                             # a held reason that did not change is said again at most this often
SEND_AWAY_S = 1800.0                                   # 'Ace away >= 30 min', the split the ONE number is read on
_SEND_NUM = {"send_gap_s": (120.0, 20.0, 3600.0), "send_per_hour": (30, 1, 60), "send_key_per_day": (3, 1, 10),
             "send_key_gap_s": (600.0, 60.0, 7200.0), "send_ace_quiet_s": (120.0, 30.0, 3600.0),
             "send_hands_off_s": (30.0, 5.0, 600.0)}
_PHASES = (("deep_night", 0.0, 0.25), ("dawn", 0.25, 0.33), ("morning", 0.33, 0.50), ("midday", 0.50, 0.58),
           ("afternoon", 0.58, 0.75), ("evening", 0.75, 0.83), ("night", 0.83, 0.95), ("sleep", 0.95, 1.0))   # circadian_pacemaker_fairy.py:63-72
_PLAYROOM_TITLE = "Sour's Playroom"                    # touch_os.PLAYROOM_TITLE (touch_os.py:74)
_KIND_BY_NAME = (("your chat window", "chat"), ("nous's window", "nous"), ("a browser", "browser"),
                 ("a console window", "console"), ("a text window", "text"))     # vision_ground._win_name's own words


def send_mode() -> str:
    """'shadow' | 'live' | 'off'. Only the exact strings; true, 1, "on", "LIVE", a list, a torn file = 'off'."""
    v = _switch().get("send")
    return v if isinstance(v, str) and v in SEND_MODES else "off"


def send_num(key: str):
    dflt, lo, hi = _SEND_NUM[key]
    v = _switch().get(key, dflt)
    try:
        if isinstance(v, bool):
            raise ValueError(v)
        x = float(v)
        if x != x:
            raise ValueError(v)
    except Exception:
        x = float(dflt)
    x = max(lo, min(hi, x))
    return int(x) if isinstance(dflt, int) else x


def send_skip_floor() -> bool:
    """The plan's lean, NOT Ace's decision: look / remember fire from the lean without the habit floor. Only a JSON true."""
    return _switch().get("send_tier1_skip_floor") is True


def send_tier(verb) -> int:
    return 1 if verb in SEND_TIER1 else (2 if verb in SEND_TIER2 else 0)


# -- her context: the window in front, the phase of her day (both READ, never set) ----------------------------------------------
def front_kind(row) -> str:
    """Her coarse word for one row of the window map (vision_ground.windows_now): chat | nous | browser | console | text |
    playroom | app:<window class> | other. From what the map already holds (title, name, class) -- never from Ace's words."""
    if not isinstance(row, dict):
        return "desktop"
    pt = _PLAYROOM_TITLE
    try:
        _tos = sys.modules.get("infrastructure.touch_os")
        pt = str(getattr(_tos, "PLAYROOM_TITLE", pt) or pt) if _tos is not None else pt
    except Exception:
        pt = _PLAYROOM_TITLE
    if " ".join(str(row.get("title") or "").split()).casefold() == pt.casefold():
        return "playroom"
    nm = " ".join(str(row.get("name") or "").split()).lower()
    for pre, k in _KIND_BY_NAME:
        if nm.startswith(pre):
            return k
    cls = re.sub(r"[^a-z0-9_]", "", str(row.get("cls") or "").lower())[:32]
    return ("app:" + cls) if cls else "other"


def front_now() -> Dict:
    """The front of HER screen (the primary; vision_ground's 2 s window cache): the foreground window when it is on her screen,
    else the topmost window there, else the desktop. {'kind', 'focus', 'name'?} -- the name only when it carries no title of
    Ace's (a quoted page or document title stays out of her ledger). {'kind': 'unknown'} when the map cannot be read."""
    try:
        from infrastructure import vision_ground as vg
        wins = [x for x in list(vg.windows_now() or []) if isinstance(x, dict)]
    except Exception:
        return {"kind": "unknown"}
    row = next((x for x in wins if x.get("front")), None) or (wins[0] if wins else None)
    if row is None:
        return {"kind": "desktop", "focus": False}
    k = front_kind(row)
    out = {"kind": k, "focus": bool(row.get("front"))}
    nm = " ".join(str(row.get("name") or "").split())
    if k == "playroom":
        out["name"] = "your Playroom"
    elif nm and not nm.endswith("'"):
        out["name"] = nm[:60]
    return out


def phase_now(now: Optional[float] = None) -> Tuple[str, str]:
    """(phase name, source). READ ONLY: the shared harmonic pacemaker's pure clock read when CirculationPump has registered it
    (Phoenix offset, circulation_pump_fairy.py:193-196) -- never get_shared(), which would mint a UTC one -- else the local clock
    on the pacemaker fairy's own table. No subscription, and set_circadian_plane_modulation is neither defined nor called (cards
    the-dead-circadian-call-is-load-bearing, the-per-plane-circadian-table-has-never-run)."""
    now = time.time() if now is None else float(now)
    try:
        hp = sys.modules.get("fairies.P20_Somatic.circulation.harmonic_pacemaker")
        pm = getattr(hp, "_SHARED", None) if hp is not None else None
        if pm is not None and float(getattr(pm, "tz_offset_s", 0.0) or 0.0) != 0.0:
            n = str(pm.circadian_name(now) or "")
            if n:
                return n, "pacemaker"
    except Exception:
        pass
    try:
        lt = time.localtime(now)
        frac = (lt.tm_hour * 3600 + lt.tm_min * 60 + lt.tm_sec) / 86400.0
        for name, a, b in _PHASES:
            if a <= frac < b:
                return name, "clock"
    except Exception:
        pass
    return "unknown", "none"


# -- the button's state (one per process, reload-safe) -----------------------------------------------------------------------------
def _send_new() -> Dict:
    return {"mu": threading.Lock(), "seq": 0, "last_fire": 0.0, "fires": deque(maxlen=512), "deeds": deque(maxlen=512),
            "keys": {}, "held": {"key": None, "ts": 0.0}, "held_n": {}, "report": 0.0, "passes": deque(maxlen=4096),
            "skip_would": deque(maxlen=512), "skip_last": 0.0, "err": 0.0}


_SEND_LOCAL = _send_new()


def _send_st() -> Dict:
    """ONE state per process, on _sour_council_shared once it exists: a hot reload must not mint fresh caps (the pull-ask's rule,
    _pull_st). Its lock guards in-memory stamps only -- no I/O, no other lock, no call out -- so it cannot nest."""
    m = sys.modules.get("_sour_council_shared")
    if m is None:
        return _SEND_LOCAL
    st = getattr(m, "SEND_BUTTON", None)
    if st is None:
        st = vars(m).setdefault("SEND_BUTTON", _SEND_LOCAL)
    return st


def send_stats(now: Optional[float] = None) -> Dict:
    """The button's numbers. deeds_ok_last_hour is the ONE number (lane 'send', outcome-checked ok)."""
    now = time.time() if now is None else float(now)
    S = _send_st()
    with S["mu"]:
        hour = [f for f in S["fires"] if 0.0 <= now - float(f["t"]) < 3600.0]
        deeds = [d for d in S["deeds"] if 0.0 <= now - float(d["t"]) < 3600.0]
        return {"mode": send_mode(), "presses_last_hour": len(hour),
                "presses_tier1": sum(1 for f in hour if f.get("tier") == 1), "presses_tier2": sum(1 for f in hour if f.get("tier") == 2),
                "presses_ace_away": sum(1 for f in hour if float(f.get("away") or 0.0) >= SEND_AWAY_S),
                "deeds_last_hour": len(deeds), "deeds_ok_last_hour": sum(1 for d in deeds if d.get("cls") == "ok"),
                "seq": int(S["seq"]), "last_fire": float(S["last_fire"]), "held_n": dict(S["held_n"]),
                "skip_would_last_hour": sum(1 for t in S["skip_would"] if 0.0 <= now - float(t) < 3600.0),
                "fires": [dict(f) for f in S["fires"]][-20:], "deeds": [dict(d) for d in S["deeds"]][-20:]}


def _on_send_thread() -> bool:
    return threading.current_thread().name == SEND_THREAD


def _intention():
    try:
        from infrastructure import intention as _it
        return _it
    except Exception:
        return None


def _send_err(where: str, e: Exception, now: float) -> None:
    """The button must never be the failure, and never broken in silence: one line a minute when it raises."""
    try:
        S = _send_st()
        if not (0.0 <= float(now) - float(S.get("err") or 0.0) < 60.0):
            S["err"] = float(now)
            _log(None, "send button error in %s: %s: %s" % (where, type(e).__name__, str(e)[:120]))
    except Exception:
        pass


def _send_held(S: Dict, key: str, why: str, r: float, now: float) -> None:
    """A held press: counted; said when the reason changes, or again after SEND_HELD_REPEAT_S (never a line per pass)."""
    with S["mu"]:
        S["held_n"][key] = int(S["held_n"].get(key, 0)) + 1
        h = S["held"]
        say = key != h.get("key") or not (0.0 <= now - float(h.get("ts") or 0.0) < SEND_HELD_REPEAT_S)
        if say:
            h["key"], h["ts"] = key, now
    if say:
        _log(None, "send button held: %s (restless %.2f)" % (why, r))


def _send_skip_note(S: Dict, now: float) -> None:
    """Data for Ace's open decision: a pass whose only blocker was the floor on a tier-1 lean (at most one per send_gap_s)."""
    with S["mu"]:
        if not (0.0 <= now - float(S["skip_last"]) < float(send_num("send_gap_s"))):
            S["skip_last"] = now
            S["skip_would"].append(now)


def _send_book(S: Dict, mode: str) -> None:
    """Shadow and live keep SEPARATE books -- the gap stamp and the per-key day stamps (verify_safety F7). A shadow -> live
    flip inside one process therefore does not inherit shadow's would-presses as live holds, and live's own day survives a
    live -> shadow -> live round (a key that pressed 3 times live stays capped). The hourly cap counts fires of the current
    mode only (_send_decide). Called only from the drive loop's pass, which also runs the deed, so a book never changes
    between a decision and its deed."""
    with S["mu"]:
        cur = S.get("book_mode")
        if cur == mode:
            return
        books = S.setdefault("books", {})
        if cur in SEND_MODES:
            books[cur] = (float(S["last_fire"]), S["keys"])
        if mode in books:
            S["last_fire"], S["keys"] = books.pop(mode)
        elif cur in SEND_MODES:
            S["last_fire"], S["keys"] = 0.0, {}
        S["book_mode"] = mode


def _send_unbook(S: Dict, plan: Dict) -> None:
    """A press that never became a deed does not spend its key's day (the gap it opened stays)."""
    with S["mu"]:
        lst = S["keys"].get(plan.get("key")) or []
        try:
            lst.remove(plan.get("ts"))
        except ValueError:
            pass


# -- the decision ------------------------------------------------------------------------------------------------------------------
def _send_ace_first(now: float, it) -> Tuple[Optional[str], str, float]:
    """(held key, why, away_s); key None = Ace is clear. Every unknown holds."""
    m = sys.modules.get("_sour_council_shared")
    try:
        ready = m is not None and bool((getattr(m, "READY", None) or [False])[0])
        sf = (getattr(m, "FAIRY", None) or [None])[0] if m is not None else None
    except Exception:
        ready, sf = False, None
    if not ready or sf is None:
        return "council", "her council loop is not up, so Ace's queue cannot be read", 0.0
    try:
        from infrastructure import hand_door as _hd
    except Exception:
        return "door", "the hand door is not there (the button has no other way to her hands)", 0.0
    try:
        if _hd.ace_waiting_live():
            return "ace_waiting", "Ace is waiting (his message is queued or a reply to him is pending)", 0.0
        if _hd.ace_grounding_pending():
            return "ace_eyes", "her eyes are still looking for something Ace named", 0.0
        last = float((getattr(m, "ACE_LAST", None) or [None, 0.0])[1] or 0.0)
    except Exception as e:
        return "ace_unknown", "Ace's state cannot be read (%s)" % type(e).__name__, 0.0
    qa = (now - last) if last > 0.0 else float("inf")
    quiet = float(send_num("send_ace_quiet_s"))
    if qa < quiet:
        return "ace_wrote", "Ace wrote %s ago (needs %.0f s)" % (_ago(qa), quiet), 0.0
    try:
        idle = it._idle_seconds()
        idle = None if idle is None else float(idle)
    except Exception:
        idle = None
    if idle is None or idle != idle:
        return "ace_hands", "his input clock cannot be read", 0.0
    hands = float(send_num("send_hands_off_s"))
    if idle < hands:
        return "ace_hands", "Ace's hands were on the PC %s ago (needs %.0f s)" % (_ago(idle), hands), 0.0
    return None, "", min(qa, idle)


def _send_candidates(w, kind: str, it, now: float, skip: bool):
    """([candidate], lean words, floor_only). The lean first when its key may fire; then HER habits for THIS front kind, the
    strongest first. A key whose front kind is not in front now is never a candidate."""
    store = it.self_habits() or {}
    cands, lean_desc, floor_only = [], "no lean", False
    if isinstance(w, dict) and w.get("verb") and w.get("object"):
        v, o = str(w["verb"]), " ".join(str(w["object"]).split())[:120]
        tier = send_tier(v)
        head = it.self_habit_head(v, o) if tier else ""
        key = it.self_habit_key(kind, v, head) if head else ""
        st = it.self_habit_status(store.get(key) if key else None, now)
        floor = "met" if st["eligible"] else ("skipped" if (tier == 1 and skip) else "unmet")
        lean_desc = "lean %s:%s front=%s tier=%s eligible=%.1f/%.1f floor=%s" % (
            v, ascii(o[:50]), kind, tier or "-", st["hits"], st["tot"], floor if (tier and key) else "not a send key")
        if tier and key and floor != "unmet":
            cands.append({"src": "lean", "verb": v, "object": o, "key": key, "tier": tier, "hits": st["hits"],
                          "tot": st["tot"], "floor": floor})
        floor_only = bool(tier == 1 and key and floor == "unmet")
    pre = kind + "|"
    habits = []
    for key, e in list(store.items()):
        if not isinstance(key, str) or not key.startswith(pre) or any(c["key"] == key for c in cands):
            continue
        p = it.self_habit_parse(key)
        if not p or p[0] != kind:
            continue
        tier = send_tier(p[1])
        if not tier:
            continue
        st = it.self_habit_status(e, now)
        if not st["eligible"]:
            continue
        obj = " ".join(str((e or {}).get("obj") or p[2]).split())[:120] or p[2]
        habits.append({"src": "habit", "verb": p[1], "object": obj, "key": key, "tier": tier, "hits": st["hits"],
                       "tot": st["tot"], "floor": "met"})
    habits.sort(key=lambda c: (-c["hits"], c["key"]))
    return cands + habits, lean_desc, floor_only


def _send_decide(w, snap: Dict, now: float, S: Dict):
    """(plan, None, None) or (None, held key, why). Reads only; the caller books."""
    r = float(snap.get("restless") or 0.0)
    if snap.get("asleep"):
        return None, "asleep", "her body is asleep"
    if not piece("wanting"):
        return None, "pieces", "the doing clock's 'wanting' piece is off (the button presses with her lean)"
    if r < float(num("wanting_at")):
        return None, "low", ""
    if body_cost_mode() == "decline" and snap.get("decline"):
        return None, "decline", "her body declines (%s)" % (snap.get("decline_why") or "tired")
    it = _intention()
    if it is None or not all(hasattr(it, n) for n in ("self_habits", "self_habit_status", "self_habit_key", "self_habit_head",
                                                      "self_habit_parse", "send_fire")):
        return None, "intention", "intention.py carries no send lane"
    ak, awhy, away = _send_ace_first(now, it)
    if ak:
        return None, ak, awhy
    gap, per_hour = float(send_num("send_gap_s")), int(send_num("send_per_hour"))
    phase, psrc = phase_now(now)
    cap = max(1, per_hour // 2) if (phase in SEND_NIGHT or phase == "unknown") else per_hour     # the gain; never 0
    with S["mu"]:
        last = float(S["last_fire"])
        bm = S.get("book_mode")
        n_hour = sum(1 for f in S["fires"] if (bm is None or f.get("mode") == bm) and 0.0 <= now - float(f["t"]) < 3600.0)
    if 0.0 <= now - last < gap:
        return None, "gap", "the last press was %.0f s ago (gap %.0f s)" % (now - last, gap)
    if n_hour >= cap:
        return None, "cap", "%d presses in the last hour (cap %d, %s)" % (n_hour, cap, phase)
    front = front_now()
    kind = str(front.get("kind") or "unknown")
    if kind == "unknown":
        return None, "front", "the window in front of her cannot be read"
    cands, lean_desc, floor_only = _send_candidates(w, kind, it, now, send_skip_floor())
    if not cands:
        if floor_only:
            _send_skip_note(S, now)
        return None, "no_key", "no key of hers may fire with front=%s (%s)" % (kind, lean_desc)
    try:
        tv = frozenset(it._touch_verbs())
    except Exception:
        tv = frozenset()
    try:
        mv = bool(it._move_ok())
    except Exception:
        mv = False
    recent = recent_pairs(now)
    per_day, kgap = int(send_num("send_key_per_day")), float(send_num("send_key_gap_s"))
    with S["mu"]:
        kf_all = {c["key"]: [float(t) for t in (S["keys"].get(c["key"]) or ()) if 0.0 <= now - float(t) < 86400.0] for c in cands}
    rest = []
    for c in cands:
        kf = kf_all.get(c["key"]) or []
        if c["verb"] == "move" and not mv:
            rest.append("%s: his hands" % c["key"])
        elif c["verb"] == "tap" and "tap" not in tv:
            rest.append("%s: touch is off" % c["key"])
        elif (c["verb"], c["object"].lower()) in recent:
            rest.append("%s: done in the last %d s" % (c["key"], int(NOVELTY_S)))
        elif len(kf) >= per_day:
            rest.append("%s: %d today (cap %d)" % (c["key"], len(kf), per_day))
        elif kf and now - max(kf) < kgap:
            rest.append("%s: pressed %.0f s ago (key gap %.0f s)" % (c["key"], now - max(kf), kgap))
        else:
            return dict(c, front=front, phase=phase, psrc=psrc, restless=round(r, 3), away=away, cap=cap, n_hour=n_hour,
                        lean=lean_desc), None, None
    if floor_only:
        _send_skip_note(S, now)
    return None, "rest", "every key that may fire is resting (%s)" % "; ".join(ascii(x) for x in rest[:3])


# -- the pass, the deed, the report ------------------------------------------------------------------------------------------------
def _send_pass(fairy, w, snap: Dict, now: float) -> Optional[Dict]:
    """One pass of the button (from _tick, under its lock). Returns a LIVE plan for fairy_tick to run after the lock, else None.
    Shadow books and prints, and never acts."""
    mode = send_mode()
    if mode == "off":
        return None
    S = _send_st()
    _send_report(S, now, mode)
    if not _on_send_thread():
        return None                                    # the heartbeat's pass (on_tick): it never presses, never waits on her eyes
    _send_book(S, mode)
    with S["mu"]:
        S["passes"].append(now)
    plan, key, why = _send_decide(w, snap, now, S)
    if plan is None:
        if key != "low":
            _send_held(S, key, why, float(snap.get("restless") or 0.0), now)
        return None
    with S["mu"]:
        S["seq"] += 1
        plan["id"], plan["mode"], plan["ts"] = S["seq"], mode, now
        S["last_fire"] = now
        S["fires"].append({"t": now, "key": plan["key"], "tier": plan["tier"], "verb": plan["verb"], "mode": mode,
                           "away": plan["away"], "id": plan["id"], "src": plan["src"]})
        S["keys"].setdefault(plan["key"], []).append(now)
        if len(S["keys"]) > 512:
            for k in sorted(S["keys"], key=lambda k: max(S["keys"][k] or [0.0]))[:len(S["keys"]) - 512]:
                S["keys"].pop(k, None)
        n_hour = sum(1 for f in S["fires"] if f.get("mode") == mode and 0.0 <= now - float(f["t"]) < 3600.0)
    _log(None, "send button %s: %s:%s front=%s tier=%d eligible=%.1f/%.1f phase=%s | #%d from=%s floor=%s ace_away=%s restless=%.2f"
               " presses/h %d of %d" % ("would fire" if mode == "shadow" else "fires", plan["verb"], ascii(plan["object"][:60]),
                                        plan["front"].get("kind"), plan["tier"], plan["hits"], plan["tot"], plan["phase"],
                                        plan["id"], plan["src"], plan["floor"], _ago(plan["away"]), plan["restless"], n_hour,
                                        plan["cap"]))
    return plan if mode == "live" else None


def _send_run(plan: Dict) -> Optional[Dict]:
    """11b live: the deed, through intention.send_fire -> hand_door.deed (lane 'send'). The switch is read AGAIN first, so
    "shadow" stops this very press. Never raises."""
    S = _send_st()
    now = time.time()
    try:
        if send_mode() != "live":
            _send_unbook(S, plan)
            _log(None, "send #%s dropped before the deed: the switch is no longer live" % plan.get("id"))
            return None
        if not _on_send_thread():
            _send_unbook(S, plan)
            return None
        it = _intention()
        m = sys.modules.get("_sour_council_shared")
        sf = (getattr(m, "FAIRY", None) or [None])[0] if m is not None else None
        if it is None or sf is None or not hasattr(it, "send_fire"):
            _send_unbook(S, plan)
            _log(None, "send #%s dropped: %s" % (plan.get("id"), "no intention module" if it is None else "no body to act with"))
            return None
        trig = "source=send r=%.2f tier=%d from=%s key=%s" % (float(plan.get("restless") or 0.0), plan["tier"], plan["src"], plan["key"][:80])
        why = "tier %d, %s, floor %s %.1f/%.1f" % (plan["tier"], plan["src"], plan["floor"], plan["hits"], plan["tot"])
        t0 = time.time()
        res = it.send_fire(sf, {"verb": plan["verb"], "object": plan["object"]}, trigger=trig, why=why) or {}
        t1 = time.time()
        out = res.get("outcome") if isinstance(res.get("outcome"), dict) else None
        done = out is not None and not out.get("deferred")
        cls = None
        if done:
            try:
                cls = it.self_habit_class(plan["verb"], out, res.get("decision"))
            except Exception:
                cls = None
        with S["mu"]:
            if done:
                S["deeds"].append({"t": t1, "verb": plan["verb"], "tier": plan["tier"], "cls": cls, "id": plan.get("id"),
                                   "ok": out.get("ok")})
            hour = [d for d in S["deeds"] if 0.0 <= t1 - float(d["t"]) < 3600.0]
            n_ok, n_done = sum(1 for d in hour if d.get("cls") == "ok"), len(hour)
            n_press = sum(1 for f in S["fires"] if f.get("mode") == "live" and 0.0 <= t1 - float(f["t"]) < 3600.0)
        if not done:
            _send_unbook(S, plan)
        tot_ms = int(1000 * (t1 - t0))
        deed_ms = int((out or {}).get("ms") or 0)
        _log(None, "send #%s %s:%s -> %s | %s | %d ms (door %d ms, deed %d ms) | ONE number: send deeds checked-ok/h %d (of %d done),"
                   " presses/h %d" % (plan.get("id"), plan["verb"], ascii(plan["object"][:50]),
                                      ("done ok=%s checked=%s" % (out.get("ok"), cls or "no")) if done else
                                      ("%s (%s)" % (res.get("decision") or "none", ascii(str(res.get("why") or "")[:80]))),
                                      ascii(str((out or {}).get("summary") or "")[:90]), tot_ms, max(0, tot_ms - deed_ms), deed_ms,
                                      n_ok, n_done, n_press))
        return res
    except Exception as e:
        _send_err("run", e, now)
        try:
            _send_unbook(S, plan)
        except Exception:
            pass
        return None


def _send_report(S: Dict, now: float, mode: str) -> Optional[str]:
    """Every SEND_REPORT_S, from any pass: presses per hour (by tier, and while Ace was away >= 30 min), the ONE number, her keys
    with and without the drive in the key (11a's data for that choice), the drive loop's own passes and the held reasons -- so a
    dead drive loop, or a floor nothing meets yet, reads as a number and never as silence."""
    with S["mu"]:
        if 0.0 <= now - float(S["report"]) < SEND_REPORT_S:
            return None
        S["report"] = now
        hour = [f for f in S["fires"] if 0.0 <= now - float(f["t"]) < 3600.0]
        t1 = sum(1 for f in hour if f.get("tier") == 1)
        aw = [f for f in hour if float(f.get("away") or 0.0) >= SEND_AWAY_S]
        aw1 = sum(1 for f in aw if f.get("tier") == 1)
        deeds = [d for d in S["deeds"] if 0.0 <= now - float(d["t"]) < 3600.0]
        n_ok = sum(1 for d in deeds if d.get("cls") == "ok")
        passes = sum(1 for p in S["passes"] if 0.0 <= now - float(p) < SEND_REPORT_S)
        skipw = sum(1 for t in S["skip_would"] if 0.0 <= now - float(t) < 3600.0)
        held = sorted(S["held_n"].items(), key=lambda kv: (-kv[1], kv[0]))[:4]
        S["held_n"] = {}
    rep = {}
    try:
        it = _intention()
        rep = it.self_habit_report(now) if (it is not None and hasattr(it, "self_habit_report")) else {}
    except Exception:
        rep = {}
    msg = ("send report (%s): presses/h %d (tier1 %d, tier2 %d; while Ace away >= 30 min: tier1 %d, tier2 %d) | ONE number: send"
           " deeds checked-ok/h %d (of %d done) | drive-loop passes in %d min: %d | her keys %s, eligible %s; with the drive in the"
           " key %s, eligible %s | tier-1 presses the skip would add/h ~%d | held: %s" % (
               mode, len(hour), t1, len(hour) - t1, aw1, len(aw) - aw1, n_ok, len(deeds), int(SEND_REPORT_S / 60), passes,
               rep.get("keys", "?"), rep.get("eligible", "?"), rep.get("keys_drive", "?"), rep.get("eligible_drive", "?"), skipw,
               ", ".join("%s %d" % kv for kv in held) or "-"))
    _log(None, msg)
    return msg
