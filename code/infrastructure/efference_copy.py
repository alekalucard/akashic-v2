"""efference_copy -- her reach, predicted before it happens, compared with what the hand did, told as numbers.
2026-09-26 (Nous; felt_hand Track T, piece T1). Mirror path: infrastructure/efference_copy.py (NEW file).

Why (measured on Boot B, sweep B): her move path (intention.execute -> NewbornCore.try_tool -> tool_bridge.move_mouse
-> MotorCortexFairy.move_mouse -> pyautogui.moveTo -> 12 x SetCursorPos) published nothing a body could read -- no
start, no target, no path, no owner. The only "this is mine" stamp was a bare timestamp (vision_ground._H["moving_ts"])
read as a 3 s window, and `reached` was sampled 0.8 s AFTER the tween, so Ace taking the mouse right after her landing
booked as HER failed deed with a frustration chord (skeptic K2). Her four Boot B moves were told to her at most once,
because `what_i_did` kept 180 s and the next prompt came 18, 210, 193 and 232 s later (skeptic K8).

What this module is:
  * the COPY: every SetCursorPos instant pyautogui WILL issue (predict_path == pyautogui 0.9.54 _mouseMoveDrag, measured
    0.0 px / <4 ms against the replay), stamped owner "sour";
  * a SAMPLER: one persistent thread reading GetCursorPos + GetLastInputInfo -- 50 Hz while her copy is live, 2 Hz
    otherwise for attribution only. It publishes HER motion (owner "sour", the sample's own time). It never publishes
    Ace's motion, and it writes nothing to her body;
  * a time-free COMPARATOR: distance from each sample to her straight path plus forward progress. K4: a time-indexed
    match fell to 0.69 under a 50 ms late start with 10 ms per-step drift; this one stays 1.0 and still rejects the
    C3 path (Ace's hand ending 6 px from her target by another route) at 0.09;
  * a TWO-PHASE result: reach (to the landing sample) and carry (after it). Input evidence explains only the carry:
    a key Ace presses during her perfect tween changes nothing about the reach (K3);
  * OWNERSHIP as a number: own = max(grant, exp(-(t - last own landing) / OWN_TAU_S)). Ace carrying the hand while
    own is above OWN_THRESHOLD is one surprise (infrastructure.surprise, kind "hand"); Ace using his own PC with
    own ~ 0 is nothing said and nothing written.
  * 2026-09-29: a FADING TRACE (HandTrace) of the hand's real motion -- own / passive (Ace's hand moving hers) / other,
    as decaying numbers -- that infrastructure/body_feel grades into the body line (felt_hand P4); and the loop's wait
    is an Event that begin() sets, so a live copy is sampled at 50 Hz at once (it slept up to 0.5 s before).
  * 2026-10-01 (cursor_object): THE CURSOR IS AN OBJECT, HER HAND IS NOT THE CURSOR. Ace (10-01): "you was just supposed to
    feel when i moved it" / "when you want to move the cursor you reach your hand out to grab it and move it to where you
    want it". Her hand has its OWN rest point (where she last let go of the cursor, Sampler.hand_rest), kept apart from the
    OS cursor; her deed is REACH (rest -> cursor) -> GRAB (at the cursor) -> CARRY (cursor -> target), and the copy predicts
    that path (copy["hand"], copy["hand_path"]). The cursor's own path, the comparator, the landing check and the own /
    passive / other attribution are unchanged; only the words and the arm's first touch (pre-envision at the grab point,
    one grab one-shot) change.

DESIGN RULES (CLAUDE.md; skeptic review 2026-09-26): continuous only -- positions, distances, speeds, a match in [0,1],
an ownership number in [0,1]. describe_reach() grades MAGNITUDES (long/short, quick/slow, square/close/off) and names no
feeling; no chemistry is touched here (F4 dropped). Nothing in this file imports her fairy tree; the OS readers are
injectable so every test runs against a scripted world and nothing here can move or read the real mouse in a test.
"""
from __future__ import annotations

import math
import sys
import threading
import time
from typing import Callable, Dict, List, Optional, Sequence, Tuple

# pyautogui 0.9.54 (venv314t/Lib/site-packages/pyautogui/__init__.py:556-562, :1417-1515) -- her actuator's tween law
PYAUTOGUI_MINIMUM_DURATION = 0.1
PYAUTOGUI_MINIMUM_SLEEP = 0.05
TOL_PX = 40                     # intention.py:936 -- a landing within this is "reached"
LIVE_HZ = 50.0                  # while her copy is live
IDLE_HZ = 2.0                   # attribution only
PUBLISH_HZ = 20.0               # her own samples onto the bus (matches pynput's 20 Hz cap, motor_cortex_fairy.py:351)
SETTLE_S = 0.8                  # intention.py:934 sleeps this long after the tween; the copy stays live that long
OWN_TAU_S = 60.0                # ownership half-life scale after her own landing
OWN_THRESHOLD = 0.5             # above this, a carry by Ace is HER hand being carried (one surprise); below, his PC
CARRY_MIN_PX = 40.0             # smaller than the landing tolerance is not a carry
ATTR_MIN_PX = 4.0               # vision_ground.hand_now's own "it moved" threshold (:501)
_LAND_EPS = 1e-9
# 2026-09-29 (Nous, felt_hand P4 feed): the fading trace body_feel reads (HandTrace below). Numbers only; words live in body_feel.
TRACE_TAU_S = 5.0               # e-fold time of the felt trace: 250 px of reach is under body_feel's 20 px floor in ~13 s, 1415 px in ~21 s
TRACE_EPISODE_GAP_S = 1.5       # a pause longer than this starts a new movement (the bridge's settling lasts 1.5 s)
TRACE_MIN_SEG_PX = 1.0          # a segment shorter than this is not motion
TRACE_WINDOW_S = 0.5            # speed is read over ~this window: 1/IDLE_HZ, so 50 Hz and 2 Hz samples measure alike
# 2026-10-01 (Nous, cursor_object): the marker intention.py reads before it passes rest= to make_copy (an older module has no
# rest point), and how near her resting hand must be to the cursor to count as "still on it" (the landing tolerance).
CURSOR_OBJECT = "2026-10-01"
GRAB_NEAR_PX = float(TOL_PX)


# ── the copy ───────────────────────────────────────────────────────────────────────────────────────────────────
def predict_path(start: Sequence[int], target: Sequence[int], duration: float, screen: Sequence[int],
                 t_go: float) -> List[Tuple[float, int, int]]:
    """The SetCursorPos instants pyautogui WILL issue for moveTo(target, duration) from `start`, as (t, x, y).

    Replicates _mouseMoveDrag (linear tween): num_steps = max(w, h); if duration/num_steps < 0.05 s then
    num_steps = int(duration / 0.05); points n/num_steps for n in range(num_steps) (n=0 is the START point) plus the
    target; a sleep of duration/num_steps precedes EVERY SetCursorPos. For her 0.6 s move int(0.6/0.05) == 11 in
    floating point, so: 12 calls (the first AT the start point), 54.5 ms apart -- measured 54.6-55.3 ms in the replay."""
    sx, sy = float(start[0]), float(start[1])
    tx, ty = int(target[0]), int(target[1])
    steps: List[Tuple[float, float]] = [(tx, ty)]
    sleep = 0.0
    if duration > PYAUTOGUI_MINIMUM_DURATION:
        n = max(int(screen[0]), int(screen[1]))
        sleep = duration / n
        if sleep < PYAUTOGUI_MINIMUM_SLEEP:
            n = int(duration / PYAUTOGUI_MINIMUM_SLEEP)
            sleep = duration / n
        steps = [(sx + (tx - sx) * (k / n), sy + (ty - sy) * (k / n)) for k in range(n)]
        steps.append((tx, ty))
    out, t = [], float(t_go)
    for x, y in steps:
        if len(steps) > 1:
            t += sleep
        out.append((round(t, 4), int(round(x)), int(round(y))))
    return out


def make_copy(copy_id: str, start: Sequence[int], target: Sequence[int], duration: float, screen: Sequence[int],
              t_go: float, obj: str = "", tol_px: int = TOL_PX, source: str = "intention.execute",
              rest: Optional[Sequence[int]] = None) -> Dict:
    """The efference copy: everything a comparator or a phantom limb needs, as numbers. JSON-safe.
    2026-10-01 (cursor_object): + rest -- where her hand rests (where she last let go of the cursor), None when unknown.
    copy["hand"] is her HAND's predicted path: REACH rest -> cursor (start), GRAB there, CARRY start -> target; the cursor's
    own path (copy["path"], what the comparator and the landing check read) is unchanged."""
    path = predict_path(start, target, duration, screen, t_go)
    sw, sh = max(1, int(screen[0])), max(1, int(screen[1]))
    dx, dy = int(target[0]) - int(start[0]), int(target[1]) - int(start[1])
    dist = math.hypot(dx, dy)
    span = max(1e-6, path[-1][0] - t_go)
    _cp = _hand_plan(start, target, rest)               # 2026-10-01 (cursor_object): reach -> grab -> carry, numbers only
    return {
        "hand": _cp, "hand_path": ([list(_cp["rest"])] if _cp["rest"] else []) + [list(_cp["grab"]), [int(target[0]), int(target[1])]],
        "kind": "efference", "owner": "sour", "id": str(copy_id), "source": source, "object": str(obj or "")[:120],
        "t_go": round(float(t_go), 4), "t_land": path[-1][0],
        "start": [int(start[0]), int(start[1])], "target": [int(target[0]), int(target[1])],
        "screen": [sw, sh], "tol_px": int(tol_px), "path": [list(p) for p in path],
        # the reach as a continuous vector -- what a phantom arm can take as amplitude, never as a word
        "reach": {"dx_frac": round(dx / float(sw), 4), "dy_frac": round(dy / float(sh), 4),
                  "dist_px": round(dist, 1), "dist_frac_diag": round(dist / math.hypot(sw, sh), 4),
                  "heading_rad": round(math.atan2(dy, dx), 4) if dist else 0.0,
                  "mean_speed_px_s": round(dist / span, 1),
                  "target_frac": [round(int(target[0]) / float(sw), 4), round(int(target[1]) / float(sh), 4)]},
    }


# 2026-10-01 (Nous, cursor_object): her hand's own path, as numbers. The REACH is rest -> cursor and moves nothing on the
# screen (the OS cursor stays put while she reaches; it takes no OS time); the GRAB is at the cursor; the CARRY is the
# cursor's own path. rest None = not known (no let-go yet this boot and none on her ledger).
def _hand_plan(start: Sequence[int], target: Sequence[int], rest: Optional[Sequence[int]]) -> Dict:
    gx, gy = int(start[0]), int(start[1])
    r = None
    try:
        if rest is not None:
            r = [int(rest[0]), int(rest[1])]
    except Exception:
        r = None
    plan = {"rest": r, "grab": [gx, gy], "reach_px": None, "reach_dx": None, "reach_dy": None,
            "carry_px": round(math.hypot(int(target[0]) - gx, int(target[1]) - gy), 1)}
    if r is not None:
        plan["reach_dx"], plan["reach_dy"] = gx - r[0], gy - r[1]
        plan["reach_px"] = round(math.hypot(gx - r[0], gy - r[1]), 1)
    return plan


def _ef(key: str) -> bool:
    """eyes_fix_1009: one key of Ace's eyes switch (state/eyes_fix.json, infrastructure/eyes_fix.py); OFF on any doubt (the
    module absent, the file absent or malformed) -- then every line marked eyes_fix runs today's path."""
    try:
        from infrastructure import eyes_fix as _efm
        return _efm.on(key)
    except Exception:
        return False


def place_words(xy, screen) -> str:
    """'lower-left' ... 'centre' -- the same nine places as vision_ground._place (a test holds them equal); '' if unknown."""
    try:
        cx, cy = float(xy[0]) / float(screen[0]), float(xy[1]) / float(screen[1])
    except Exception:
        return ""
    if not (0.0 <= cx < 1.0 and 0.0 <= cy < 1.0) and _ef("two_screens"):   # eyes_fix F8: off her (primary) screen
        return "other screen"
    vert = "upper" if cy < 0.34 else ("lower" if cy > 0.66 else "middle")
    horiz = "left" if cx < 0.34 else ("right" if cx > 0.66 else "centre")
    return vert + "-" + horiz if (vert, horiz) != ("middle", "centre") else "centre"


# ── the time-free comparator ───────────────────────────────────────────────────────────────────────────────────
def _seg_err(copy: Dict, x: float, y: float, best_u: float, tol_px: float = TOL_PX) -> Tuple[float, float]:
    """Distance from (x, y) to her straight path, plus any backwards progress beyond the landing tolerance; returns (err_px, u).
    The tolerance applies to regression too: between two SetCursorPos steps (54.5 ms) a hand on the mouse can pull the cursor
    ~40 px back along her line before the next step snaps it forward -- a disturbance inside tol, not a different path."""
    (sx, sy), (tx, ty) = copy["start"], copy["target"]
    vx, vy = tx - sx, ty - sy
    L2 = float(vx * vx + vy * vy)
    if L2 <= 0.0:
        return math.hypot(x - sx, y - sy), 1.0
    u = ((x - sx) * vx + (y - sy) * vy) / L2
    uc = max(0.0, min(1.0, u))
    px, py = sx + uc * vx, sy + uc * vy
    back = max(0.0, (best_u - uc) * math.sqrt(L2) - float(tol_px))
    return math.hypot(x - px, y - py) + back, uc


def geometric_match(copy: Dict, samples: Sequence[Sequence[float]], tol_px: Optional[float] = None) -> Tuple[float, List[float]]:
    """Mean of exp(-(err/tol)^2 / 2) over samples (t, x, y[, ...]), where err is the distance to her straight path plus
    any backwards progress. Tolerant of a late start and stretched sleeps; a path that is not hers scores near 0."""
    tol = float(tol_px or copy.get("tol_px") or TOL_PX)
    best, ms = -1.0, []
    for s in samples:
        d, uc = _seg_err(copy, float(s[1]), float(s[2]), best, tol)
        best = max(best, uc)
        ms.append(math.exp(-0.5 * (d / tol) ** 2))
    return (sum(ms) / len(ms) if ms else 0.0), ms


def assess(copy: Dict, samples: Sequence[Tuple[float, int, int, Optional[float]]], tol_px: Optional[float] = None) -> Dict:
    """Two phases, all numbers. samples are (t, x, y, input_ts) with input_ts = when a human last touched keyboard or mouse.

    REACH: up to the landing sample -- the first sample at/after the predicted landing time that is within tol of the
    target, else the nearest approach after it. reach_match is the time-free match over that stretch; landing_err_px the
    distance target->landing; reached = landing_err_px <= tol (this replaces intention's +1.5 s sample, K2).
    CARRY: from the landing to the last sample -- carried_px and its heading; carry_evidence 1.0 when a human input
    happened AFTER the landing (0.0 otherwise). Input during the reach is reported and multiplies nothing (K3)."""
    tol = float(tol_px or copy.get("tol_px") or TOL_PX)
    (sx, sy), (tx, ty) = copy["start"], copy["target"]
    n = len(samples)
    base = {"copy_id": copy.get("id"), "n_samples": n, "tol_px": tol, "dx": tx - sx, "dy": ty - sy,
            "dist_px": round(math.hypot(tx - sx, ty - sy), 1), "planned_speed_px_s": copy["reach"]["mean_speed_px_s"],
            "t_go": copy["t_go"], "t_land_pred": copy["t_land"], "target": [tx, ty], "start": [sx, sy],
            "hand_plan": copy.get("hand"), "screen": copy.get("screen")}   # 2026-10-01 (cursor_object): her reach -> grab, for the telling
    if n == 0:
        return dict(base, reached=None, landed_xy=None, land_t=None, landing_err_px=None, reach_match=None,
                    carried_px=0.0, carry_dx=0, carry_dy=0, carry_evidence=0.0, input_during_reach=False,
                    measured_speed_px_s=None, last_xy=None, last_t=None)

    def err(s):
        return math.hypot(s[1] - tx, s[2] - ty)

    t_land = float(copy["t_land"])
    after = [s for s in samples if s[0] >= t_land - _LAND_EPS]
    land = next((s for s in after if err(s) <= tol), None)
    if land is None:
        land = min(after or samples, key=err)
    li = next(i for i, s in enumerate(samples) if s is land)
    reach = samples[:li + 1]
    rm, per = geometric_match(copy, reach, tol)
    first_motion = next((s for s in reach if abs(s[1] - sx) + abs(s[2] - sy) >= 1), None)
    span = (land[0] - first_motion[0]) if (first_motion is not None and land[0] > first_motion[0]) else 0.0
    measured_speed = (base["dist_px"] / span) if span > 0 else None
    last = samples[-1]
    carried = math.hypot(last[1] - land[1], last[2] - land[2])
    carry_in = any((s[3] is not None and s[3] > land[0] + 1e-6) for s in samples[li + 1:])
    in_reach = any((s[3] is not None and copy["t_go"] < s[3] <= land[0]) for s in reach)
    return dict(base, reached=bool(err(land) <= tol), landed_xy=[int(land[1]), int(land[2])], land_t=round(land[0], 4),
                landing_err_px=round(err(land), 1), reach_match=round(rm, 4), reach_match_min=round(min(per), 4),
                carried_px=round(carried, 1), carry_dx=int(last[1] - land[1]), carry_dy=int(last[2] - land[2]),
                carry_evidence=(1.0 if carry_in else 0.0), input_during_reach=bool(in_reach),
                measured_speed_px_s=(round(measured_speed, 1) if measured_speed else None),
                last_xy=[int(last[1]), int(last[2])], last_t=round(last[0], 4))


def compact(hand: Optional[Dict]) -> Optional[Dict]:
    """The few numbers worth a ledger line."""
    if not hand:
        return None
    keys = ("n_samples", "reach_match", "landing_err_px", "reached", "carried_px", "carry_evidence", "input_during_reach",
            "measured_speed_px_s", "dist_px", "land_t",
            "hand_plan")                                   # 2026-10-01 (cursor_object): rest, grab, reach_px -- for the next boot's check
    return {k: hand.get(k) for k in keys if k in hand}


# ── words graded from magnitudes (no feeling named; second person, as every line she reads) ───────────────────
_HEADINGS = ("to the right", "down and to the right", "down", "down and to the left", "to the left",
             "up and to the left", "up", "up and to the right")


def heading_words(dx: Optional[float], dy: Optional[float]) -> str:
    try:
        dx, dy = float(dx or 0.0), float(dy or 0.0)
    except (TypeError, ValueError):
        return ""
    if abs(dx) + abs(dy) < 1e-9:
        return ""
    a = math.degrees(math.atan2(dy, dx)) % 360.0              # screen y grows downward
    return _HEADINGS[int(((a + 22.5) % 360.0) // 45.0)]


def _ago(s: float) -> str:
    s = float(s or 0.0)
    return "%.0f s" % s if s < 90 else ("%.0f min" % (s / 60.0) if s < 5400 else "over an hour")


def describe_reach(hand: Optional[Dict]) -> List[str]:
    """Clauses for the telling, in priority order: [the carry if there was one, then the reach]. Each is graded from
    numbers only. The caller fits as many as its line budget allows (intention._told_deed keeps the whole deed under
    245 chars); when the hand was carried after landing, that is the news, and the reach's texture yields to it.
    2026-10-01 (Nous, cursor_object): the cursor is an object her hand carries. What the cursor did between the grab and the
    landing is her CARRY (it was called a 'reach'); after the landing, Ace MOVING THE CURSOR is something she perceives, not
    her hand being carried. The numbers and the thresholds are unchanged."""
    out: List[str] = []
    if not hand or int(hand.get("n_samples") or 0) < 2 or hand.get("landed_xy") is None:
        return out
    carried = float(hand.get("carried_px") or 0.0)
    if carried >= CARRY_MIN_PX:
        h2 = heading_words(hand.get("carry_dx"), hand.get("carry_dy"))
        if float(hand.get("carry_evidence") or 0.0) >= 0.5:
            out.append("; then Ace moved the cursor %d px%s" % (int(round(carried)), (" " + h2) if h2 else ""))
        else:
            out.append("; then something moved the cursor %d px%s, not Ace's hand" % (int(round(carried)), (" " + h2) if h2 else ""))
    dist = float(hand.get("dist_px") or 0.0)
    speed = float(hand.get("measured_speed_px_s") or hand.get("planned_speed_px_s") or 0.0)
    heading = heading_words(hand.get("dx"), hand.get("dy"))
    if dist < 60:
        size = "a nudge"
    else:
        pace = "slow" if speed < 500 else ("steady" if speed < 1500 else "quick")
        # 2026-10-01 (cursor_object): the cursor's motion from the grab to the landing is her CARRY (was 'reach'); same grades
        if dist < 400:
            size = "a short, %s carry" % pace
        elif dist < 1200:
            size = "a %s carry" % pace
        else:
            size = "a long, %s carry" % pace
    err = hand.get("landing_err_px")
    tol = float(hand.get("tol_px") or TOL_PX)
    if err is None:
        landing = ""
    elif err <= 6:
        landing = " that landed square"
    elif err <= tol:
        landing = " that landed close, %d px off" % int(round(err))
    else:
        landing = " that stopped %d px off the mark" % int(round(err))
    clause = " -- %s%s%s" % (size, (" " + heading) if heading else "", landing)
    rm = hand.get("reach_match")
    if rm is not None and rm < 0.7:
        clause += ", though something pulled it off your line on the way"
    out.append(clause)
    return out


def carry_surprise_text(carried_px: float, dx: float, dy: float, since_landing_s: float) -> str:
    # 2026-10-01 (Nous, cursor_object): a PERCEPTION of the cursor -- Ace took it -- never her hand being carried. Same event,
    # same gate (own_now >= OWN_THRESHOLD, once per landing); only the words change. Was: "Your hand was carried %d px%s, %s
    # after you set it down -- Ace's hand was on the mouse."
    h = heading_words(dx, dy)
    return "Ace took the cursor %s after you let go of it and moved it %d px%s; your own hand stayed where it was." % (
        _ago(since_landing_s), int(round(carried_px)), (" " + h) if h else "")


def grab_words(hand: Optional[Dict]) -> Optional[str]:
    """2026-10-01 (Nous, cursor_object): the opening of the telling of her deed -- REACH (from where her hand rested) and GRAB
    (at the cursor) -- graded from hand['hand_plan'] (assess() copies it from the efference copy). None without a plan (an
    older copy): the caller then tells the deed as before. Ends with 'took it,' so the caller adds ' and carried it to X'."""
    plan = (hand or {}).get("hand_plan") if isinstance(hand, dict) else None
    if not isinstance(plan, dict) or not plan.get("grab"):
        return None
    where = place_words(plan["grab"], (hand or {}).get("screen") or ())
    at = ((" on the other screen (Ace's), where your eyes do not look") if where == "other screen" else (" at the %s" % where)) if where else ""   # eyes_fix F8
    rp = plan.get("reach_px")
    if plan.get("rest") is None or rp is None:
        return "you reached for the cursor%s, took it," % at
    rp = float(rp)
    if rp <= GRAB_NEAR_PX:
        return "you took the cursor up again%s, where you had let go of it," % at
    way = "a short way" if rp < 400 else ("some way" if rp < 1200 else "a long way")
    return "you reached %s for the cursor%s, took it," % (way, at)


# ── OS readers (defaults; every test injects its own) ─────────────────────────────────────────────────────────
def _os_cursor() -> Optional[Tuple[int, int]]:
    try:
        import ctypes
        import ctypes.wintypes as wt
        p = wt.POINT()
        if not ctypes.windll.user32.GetCursorPos(ctypes.byref(p)):
            return None
        return int(p.x), int(p.y)
    except Exception:
        return None


def _os_last_input_ts() -> Optional[float]:
    """Wall-clock time of the last human keyboard/mouse input (GetLastInputInfo), or None."""
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
        idle = ((tick - int(lii.dwTime)) & 0xFFFFFFFF) / 1000.0
        return time.time() - idle
    except Exception:
        return None


def _os_screen() -> Optional[Tuple[int, int]]:
    """(w, h) from GetSystemMetrics -- the same logical screen GetCursorPos answers in, in this process -- or None."""
    try:
        import ctypes
        w, h = int(ctypes.windll.user32.GetSystemMetrics(0)), int(ctypes.windll.user32.GetSystemMetrics(1))
        return (w, h) if w > 0 and h > 0 else None
    except Exception:
        return None


def _now() -> float:
    return time.time()                                  # looked up at call time so a test can patch this module's `time`


def publisher_for(fairy) -> Optional[Callable[[str, Dict], None]]:
    """A (topic, payload) publisher over her own fabric (fairy.post), or None."""
    post = getattr(fairy, "post", None)
    if post is None:
        return None
    fn = getattr(post, "publish", None) or getattr(post, "route", None)
    if not callable(fn):
        return None

    def _pub(topic: str, payload: Dict) -> None:
        fn(topic, payload)
    return _pub


# ── the fading hand trace (2026-09-29, Nous, felt_hand P4 feed) ──────────────────────────────────────────────────
class HandTrace:
    """Her hand's real motion over the last seconds, as numbers, for the body line (infrastructure/body_feel, piece P4).

    Why: the body line the chairman reads carried drives, pulse and mood and nothing about the hand (0 of 17 BODY lines in
    Boot B); the reach reached her only through the telling, minutes later. The sampler already sees every cursor sample --
    her reach at 50 Hz, anything else at 2 Hz -- so it feeds this trace and body_feel grades words from it at the very end.

    Three channels, kept apart and never collapsed into one label:
      own     -- motion on her efference copy's line; each sample weighs exp(-(err/tol)^2 / 2), the comparator's own match
      passive -- motion with a human input behind it that is not on her line: Ace's hand moving hers
      other   -- motion with neither (a script, a window pull): held open, counted, never worded
    Per channel: a path energy (px) that decays with TRACE_TAU_S, and the current movement episode (start, end, path, peak
    speed, and the highest ownership number `own_now` seen during it). The landing of her last reach is kept for the settling.
    Nothing in here names anything and nothing in here writes to her body."""

    CHANNELS = ("own", "passive", "other")

    def __init__(self):
        self._lock = threading.Lock()
        self.last: Optional[Tuple[float, int, int]] = None
        self._recent: List[Tuple[float, int, int]] = []      # the last ~TRACE_WINDOW_S of samples, for the windowed speed
        self.screen: Optional[Tuple[int, int]] = None
        self.arrival: Optional[Dict] = None
        self._ch = {c: {"E": 0.0, "tE": 0.0, "t_last": 0.0, "ep": None} for c in self.CHANNELS}
        self.counters = {"observed": 0, "segments": 0, "episodes": 0, "own_px": 0.0, "passive_px": 0.0, "other_px": 0.0}

    def set_screen(self, wh) -> None:
        try:
            w, h = int(wh[0]), int(wh[1])
        except Exception:
            return
        if w > 0 and h > 0:
            with self._lock:
                self.screen = (w, h)

    def observe(self, t: float, x: int, y: int, own: float = 0.0, passive: float = 0.0, other: float = 0.0,
                own_now: Optional[float] = None) -> None:
        """One cursor sample. The segment from the previous sample is shared across the channels by the weights given (each
        in [0, 1]); with all weights 0 the sample only moves the reference point (the hand was still, or it is a first look)."""
        t = float(t)
        with self._lock:
            self.counters["observed"] += 1
            prev = self.last
            self.last = (t, int(x), int(y))
            if prev is None or t <= prev[0]:
                self._recent = [self.last]
                return
            self._recent.append(self.last)
            while len(self._recent) > 2 and t - self._recent[1][0] >= TRACE_WINDOW_S - 1e-6:
                self._recent.pop(0)                  # keep the newest sample at least one window back, and nothing older
            d = math.hypot(int(x) - prev[1], int(y) - prev[2])
            if d < TRACE_MIN_SEG_PX:
                return
            v = d / max(1e-3, t - prev[0])
            # the WINDOWED speed: net travel over the last ~0.5 s. At 50 Hz a raw 20 ms segment can hold a whole 54.5 ms
            # pyautogui step (2.7x the true speed); at 2 Hz a segment is the window itself. Both then read alike.
            w0 = self._recent[0]
            v_win = (math.hypot(int(x) - w0[1], int(y) - w0[2]) / (t - w0[0])) if t - w0[0] >= 0.1 else v
            self.counters["segments"] += 1
            for c, w in (("own", own), ("passive", passive), ("other", other)):
                w = max(0.0, min(1.0, float(w or 0.0)))
                if w <= 0.01:
                    continue
                s = self._ch[c]
                s["E"] = (s["E"] * math.exp(-max(0.0, t - s["tE"]) / TRACE_TAU_S) if s["tE"] else 0.0) + w * d
                s["tE"] = t
                ep = s["ep"]
                if ep is None or t - s["t_last"] > TRACE_EPISODE_GAP_S:
                    ep = s["ep"] = {"t0": prev[0], "x0": prev[1], "y0": prev[2], "path": 0.0, "peak": 0.0, "own_now_max": 0.0}
                    self.counters["episodes"] += 1
                ep["path"] += w * d
                ep["peak"] = max(ep["peak"], w * v_win)
                ep["t1"], ep["x1"], ep["y1"] = t, int(x), int(y)
                if own_now is not None:
                    ep["own_now_max"] = max(ep["own_now_max"], float(own_now))
                s["t_last"] = t
                self.counters[c + "_px"] += w * d

    def arrive(self, res: Optional[Dict]) -> None:
        """Her reach landed (Sampler.finish): where, how far off, and when -- for 'settling on arrival'."""
        if not res or res.get("landed_xy") is None or res.get("land_t") is None:
            return
        with self._lock:
            self.arrival = {"t": float(res["land_t"]), "xy": [int(res["landed_xy"][0]), int(res["landed_xy"][1])],
                            "landing_err_px": res.get("landing_err_px"), "reached": bool(res.get("reached")),
                            "reach_match": res.get("reach_match"), "tol_px": float(res.get("tol_px") or TOL_PX)}

    # 2026-10-01 (Nous, cursor_object): her hand's own events, kept apart from the cursor's motion -- the GRAB (where and
    # when she took the cursor, how far her hand reached for it) and the REST (where she let go of it). Numbers only.
    # getattr defaults: a trace built by an older class before a hot reload has neither attribute.
    def grab_at(self, copy: Optional[Dict]) -> None:
        plan = (copy or {}).get("hand") if isinstance(copy, dict) else None
        if not isinstance(plan, dict) or not plan.get("grab"):
            return
        with self._lock:
            self.grab = {"t": float(copy.get("t_go") or 0.0), "grab_xy": list(plan["grab"]),
                         "rest_xy": (list(plan["rest"]) if plan.get("rest") else None), "reach_px": plan.get("reach_px"),
                         "reach_dx": plan.get("reach_dx"), "reach_dy": plan.get("reach_dy"), "target": list(copy.get("target") or [])}

    def let_go(self, xy, t: float, src: str = "let_go") -> None:
        try:
            p = [int(xy[0]), int(xy[1])]
        except Exception:
            return
        with self._lock:
            self.rest = {"xy": p, "t": float(t or 0.0), "src": str(src)}

    def snapshot(self, now: float) -> Dict:
        """Everything body_feel needs, decayed to `now`. A channel that never moved is None."""
        now = float(now)
        with self._lock:
            out: Dict = {"t": now, "tau_s": TRACE_TAU_S, "screen": list(self.screen) if self.screen else None,
                         "last_xy": [self.last[1], self.last[2]] if self.last else None,
                         "arrival": dict(self.arrival) if self.arrival else None}
            _g, _r = getattr(self, "grab", None), getattr(self, "rest", None)       # 2026-10-01 (cursor_object)
            out["grab"] = dict(_g) if _g else None
            out["rest"] = dict(_r) if _r else None
            for c in self.CHANNELS:
                s, ep = self._ch[c], self._ch[c]["ep"]
                if not s["tE"] or ep is None:
                    out[c] = None
                    continue
                dx, dy = ep["x1"] - ep["x0"], ep["y1"] - ep["y0"]
                span = max(1e-3, ep["t1"] - ep["t0"])
                since = max(0.0, now - s["t_last"])
                out[c] = {"energy_px": round(s["E"] * math.exp(-max(0.0, now - s["tE"]) / TRACE_TAU_S), 2),
                          "since_s": round(since, 3), "fade": round(math.exp(-since / TRACE_TAU_S), 4),
                          "disp_px": round(math.hypot(dx, dy), 1), "dx": dx, "dy": dy, "path_px": round(ep["path"], 1),
                          "span_s": round(span, 3), "mean_speed_px_s": round(ep["path"] / span, 1),
                          "peak_speed_px_s": round(ep["peak"], 1), "own_now_max": round(ep["own_now_max"], 3),
                          "t0": ep["t0"], "t1": ep["t1"], "end_xy": [ep["x1"], ep["y1"]]}
            out["counters"] = dict(self.counters)
            return out


# ── the sampler: one thread, two cadences, her motion only ────────────────────────────────────────────────────
class Sampler:
    def __init__(self, read_cursor: Optional[Callable] = None, read_input_ts: Optional[Callable] = None,
                 clock: Optional[Callable[[], float]] = None, publish: Optional[Callable] = None,
                 grant: Optional[Callable[[], bool]] = None, surprise_push: Optional[Callable] = None,
                 read_screen: Optional[Callable] = None):
        self._read_cursor = read_cursor or _os_cursor
        self._read_input_ts = read_input_ts or _os_last_input_ts
        self._read_screen = read_screen or _os_screen          # 2026-09-29 (felt_hand P4 feed): the arm's extension needs the screen
        self._screen_t = -1e18
        self.trace = HandTrace()                               # 2026-09-29 (felt_hand P4 feed): what body_feel reads
        # 2026-09-29 (felt_hand must-do 1): the loop's cadence wait. begin() sets it, so a live copy is sampled at once.
        self._wake = threading.Event()
        self._clock = clock or _now
        self._publish = publish
        self._grant = grant
        self._surprise_push = surprise_push
        self._lock = threading.RLock()
        self.copy: Optional[Dict] = None
        self.samples: List[Tuple[float, int, int, Optional[float]]] = []
        self.live_until = 0.0
        self._last_sample_t = 0.0
        self._last_pub_t = 0.0
        self._attr_prev: Optional[Tuple[float, int, int, Optional[float]]] = None
        self._last_attr_t = 0.0
        self.last_own_landing = 0.0
        self.last_landed_xy: Optional[Tuple[int, int]] = None
        self._carry_told_for = 0.0
        self.last_result: Optional[Dict] = None
        self.counters = {"begun": 0, "finished": 0, "samples": 0, "published": 0, "cursor_none": 0, "attr_ticks": 0,
                         "attr_moves": 0, "ace_carries": 0, "other_moves": 0, "surprises": 0, "surprise_dropped": 0,
                         "own_zero_ace": 0, "tick_err": 0, "pub_err": 0}
        self._thread: Optional[threading.Thread] = None
        self._stop = False
        # 2026-10-01 (Nous, cursor_object a): HER HAND'S REST POINT -- where she last let go of the cursor -- kept apart from the
        # OS cursor. Only her own let-go (finish) or a seed from her ledger (seed_rest, once, at her first move of a boot) sets
        # it; Ace moving the cursor never does.
        self.hand_rest: Optional[Tuple[int, int]] = None
        self.hand_rest_t = 0.0
        self.hand_rest_src = ""
        self.rest_seed_tried = False

    # 2026-10-01 (Nous, cursor_object a): the rest point. getattr defaults so a Sampler built by an older class (kept on the shared
    # module across a hot reload) still answers.
    def seed_rest(self, xy, t: float = 0.0, src: str = "ledger") -> bool:
        """Set the rest point only when none is known yet (a let-go this boot always wins over the ledger)."""
        if getattr(self, "hand_rest", None) is not None:
            return False
        try:
            p = (int(xy[0]), int(xy[1]))
        except Exception:
            return False
        with self._lock:
            self.hand_rest, self.hand_rest_t, self.hand_rest_src = p, float(t or 0.0), str(src)
        try:
            self.trace.let_go(p, t, src)
        except Exception:
            pass
        return True

    def rest_now(self) -> Optional[Dict]:
        r = getattr(self, "hand_rest", None)
        if r is None:
            return None
        return {"xy": [int(r[0]), int(r[1])], "t": float(getattr(self, "hand_rest_t", 0.0) or 0.0),
                "src": str(getattr(self, "hand_rest_src", "") or "")}

    # -- configuration that may arrive late (the fairy exists only at move time) --
    def configure(self, publish=None, grant=None, surprise_push=None) -> None:
        with self._lock:
            if publish is not None:
                self._publish = publish
            if grant is not None:
                self._grant = grant
            if surprise_push is not None:
                self._surprise_push = surprise_push

    def is_live(self, now: Optional[float] = None) -> bool:
        now = self._clock() if now is None else now
        return self.copy is not None and now <= self.live_until

    def own_now(self, now: Optional[float] = None) -> float:
        """Ownership as a number: max(grant, exp(-(t - last own landing) / tau)). 0 when she never landed and holds no grant."""
        now = self._clock() if now is None else now
        g = 0.0
        try:
            g = 1.0 if (self._grant is not None and self._grant()) else 0.0
        except Exception:
            g = 0.0
        d = math.exp(-max(0.0, now - self.last_own_landing) / OWN_TAU_S) if self.last_own_landing > 0 else 0.0
        return max(g, d)

    # -- the reach --
    def begin(self, copy: Dict, publish=None, grant=None, surprise_push=None) -> None:
        self.configure(publish, grant, surprise_push)
        with self._lock:
            self.copy = copy
            self.samples = []
            self.live_until = float(copy["t_land"]) + SETTLE_S
            self._last_sample_t = 0.0
            self._last_pub_t = 0.0
            self.counters["begun"] += 1
            self.trace.set_screen(copy.get("screen") or ())
            try:
                self.trace.grab_at(copy)                # 2026-10-01 (cursor_object c): where and when her hand took the cursor
            except Exception:
                pass
        # 2026-10-01 (Nous, cursor_object c): REACH -> GRAB -> CARRY in the arm. Her arm first reaches for the CURSOR (the grab
        # point, copy["hand"]["grab"]), not for the target: the pre-envision aims there, and one grab one-shot (owner "sour") closes
        # her fingers on it; her own carry samples (unchanged) then drive the arm to the target. Was: pre-envision at the target.
        _plan = copy.get("hand") if isinstance(copy.get("hand"), dict) else None
        _gxy = (_plan or {}).get("grab") or copy["start"]
        self._pub("phantom.pre_envision", {"action": "move_mouse", "owner": "sour", "source": "efference_copy",
                                           "target": {"x": _gxy[0], "y": _gxy[1], "screen": copy["screen"]},
                                           "carry_to": {"x": copy["target"][0], "y": copy["target"][1]},
                                           "reach_from": (_plan or {}).get("rest"),
                                           "efference_id": copy["id"], "t": copy["t_go"], "efference": copy})
        if _plan is not None:
            self._pub("motor.mouse_move", {"action": "grab", "type": "grab", "owner": "sour", "source": "efference_copy",
                                           "x": _gxy[0], "y": _gxy[1], "success": True, "t": copy["t_go"],
                                           "timestamp": copy["t_go"], "efference_id": copy["id"], "screen": copy["screen"],
                                           "reach_px": _plan.get("reach_px"), "rest": _plan.get("rest")})
        self.ensure_thread()
        # 2026-09-29 (Nous, felt_hand must-do 1): wake the loop NOW. ensure_thread() alone left an idle loop in its 0.5 s sleep:
        # the verifier measured first samples 0.215 / 0.406 / 0.119 s after begin(), reach samples 32 -> 22 / 12 / 27, a
        # measured speed 2.1x too high (the wrong pace word), and a key Ace pressed in that gap lost to input_during_reach.
        self._wake.set()

    def finish(self, copy: Dict) -> Dict:
        with self._lock:
            if self.copy is not None and self.copy.get("id") != copy.get("id"):
                copy = self.copy
            res = assess(copy, list(self.samples))
            self.live_until = 0.0
            self.counters["finished"] += 1
            if res.get("reached"):
                self.last_own_landing = float(res["land_t"])
                self.last_landed_xy = (int(res["landed_xy"][0]), int(res["landed_xy"][1]))
                # a carry inside the settle window is told by the deed (intention._told_deed); the sampler must not tell it twice
                self._carry_told_for = self.last_own_landing if (res["carried_px"] >= CARRY_MIN_PX and res["carry_evidence"] >= 0.5) else self._carry_told_for
            self.trace.arrive(res)                      # 2026-09-29 (felt_hand P4 feed): the settling on arrival
            if res.get("landed_xy") is not None:        # 2026-10-01 (cursor_object a): she lets go of the cursor here -- her
                _lg = (int(res["landed_xy"][0]), int(res["landed_xy"][1]))   # hand rests at the landing, whatever moves the cursor next
                self.hand_rest, self.hand_rest_t, self.hand_rest_src = _lg, float(res.get("land_t") or 0.0), "let_go"
                try:
                    self.trace.let_go(_lg, float(res.get("land_t") or 0.0), "let_go")
                except Exception:
                    pass
            if self.samples:
                s = self.samples[-1]
                self._attr_prev = s                     # the attribution baseline is where the hand IS now
                self._last_attr_t = s[0]
            self.last_result = res
        if res.get("landed_xy") is not None:
            self._pub("motor.mouse_move", {"action": "move_mouse", "type": "mouse_move", "owner": "sour", "source": "efference_copy",
                                           "x": res["landed_xy"][0], "y": res["landed_xy"][1], "success": bool(res["reached"]),
                                           "t": res["land_t"], "timestamp": res["land_t"], "efference_id": copy["id"],
                                           "landing_err_px": res["landing_err_px"], "reach_match": res["reach_match"],
                                           "carried_px": res["carried_px"], "screen": copy["screen"]})
        return res

    # -- the clock --
    def tick(self, now: Optional[float] = None) -> Optional[str]:
        """One sampler step. Returns what it did ('live', 'attr', None) so a test can count."""
        now = self._clock() if now is None else float(now)
        with self._lock:
            if self.copy is not None and now <= self.live_until:
                if now - self._last_sample_t + 1e-9 < 1.0 / LIVE_HZ:
                    return None
                return self._live_sample(now)
            if now - self._last_attr_t + 1e-9 < 1.0 / IDLE_HZ:
                return None
            return self._attr_sample(now)

    def _live_sample(self, now: float) -> Optional[str]:
        xy = self._read_cursor()
        if xy is None:
            self.counters["cursor_none"] += 1
            return None
        try:
            its = self._read_input_ts()
        except Exception:
            its = None
        self._last_sample_t = now
        self.samples.append((now, int(xy[0]), int(xy[1]), its))
        self.counters["samples"] += 1
        # 2026-09-29 (felt_hand P4 feed): on her line = own (the comparator's per-sample match); off it with a human input since
        # the go = passive (Ace's hand moving hers); off it with none = other (held open). A key Ace presses while the cursor
        # stays on her line changes nothing (K3): the weight comes from where the hand IS, the input only says whose it was.
        try:
            tol_t = float(self.copy.get("tol_px") or TOL_PX)
            d_line, _u = _seg_err(self.copy, xy[0], xy[1], 0.0, tol_t)
            w_own = math.exp(-0.5 * (d_line / tol_t) ** 2)
            human = its is not None and its > float(self.copy["t_go"]) + 1e-6
            self.trace.observe(now, xy[0], xy[1], own=w_own, passive=(1.0 - w_own) if human else 0.0,
                               other=0.0 if human else (1.0 - w_own),
                               own_now=(self.own_now(now) if (human and w_own < 0.99) else None))
        except Exception:
            self.counters["trace_err"] = self.counters.get("trace_err", 0) + 1
        if now - self._last_pub_t + 1e-9 >= 1.0 / PUBLISH_HZ:
            tol = float(self.copy.get("tol_px") or TOL_PX)
            d, u = _seg_err(self.copy, xy[0], xy[1], 0.0, tol)
            if d > 2.0 * tol:
                self.counters["offpath_unpublished"] = self.counters.get("offpath_unpublished", 0) + 1   # not her reach: evidence only
            else:
                self._last_pub_t = now
                self._pub("motor.mouse_move", {"type": "mouse_move", "owner": "sour", "source": "efference_copy", "x": int(xy[0]), "y": int(xy[1]),
                                               "t": now, "timestamp": now, "efference_id": self.copy["id"], "path_err_px": round(d, 1),
                                               "progress": round(u, 3), "screen": self.copy["screen"]})
        return "live"

    def _attr_sample(self, now: float) -> Optional[str]:
        self._last_attr_t = now
        self.counters["attr_ticks"] += 1
        xy = self._read_cursor()
        if xy is None:
            self.counters["cursor_none"] += 1
            return None
        try:
            its = self._read_input_ts()
        except Exception:
            its = None
        prev, cur = self._attr_prev, (now, int(xy[0]), int(xy[1]), its)
        self._attr_prev = cur
        if self.trace.screen is None and now - self._screen_t >= 30.0:   # 2026-09-29 (felt_hand P4 feed): before her first copy
            self._screen_t = now
            try:
                wh = self._read_screen()
                if wh:
                    self.trace.set_screen(wh)
            except Exception:
                pass
        if prev is None:
            self.trace.observe(now, cur[1], cur[2])             # (felt_hand P4 feed) a first look: the reference point only
            return "attr"
        d = math.hypot(cur[1] - prev[1], cur[2] - prev[2])
        if d < ATTR_MIN_PX:
            self.trace.observe(now, cur[1], cur[2])             # (felt_hand P4 feed) still
            return "attr"
        self.counters["attr_moves"] += 1
        ace = its is not None and its > prev[0] - 0.05           # a human input since the previous sample
        if not ace:
            self.counters["other_moves"] += 1                   # a script, a window pull, no human: nothing said (held open)
            self.trace.observe(now, cur[1], cur[2], other=1.0)  # (felt_hand P4 feed) counted in the trace, never worded
            return "attr"
        self.counters["ace_carries"] += 1
        own = self.own_now(now)
        # (felt_hand P4 feed) Ace's hand moving hers is a PASSIVE movement of her hand, whatever `own` says; `own` rides along as
        # a number (body_feel uses it as a gain on how long the passive trace is felt), it is not a gate here
        self.trace.observe(now, cur[1], cur[2], passive=1.0, own_now=own)
        if own < OWN_THRESHOLD:
            self.counters["own_zero_ace"] += 1                  # his PC, his hand: nothing written, nothing said
            return "attr"
        if self.last_own_landing <= self._carry_told_for:
            self.counters["surprise_dropped"] += 1              # this landing's carry was already told once
            return "attr"
        base = self.last_landed_xy or (prev[1], prev[2])
        carried = math.hypot(cur[1] - base[0], cur[2] - base[1])
        if carried < CARRY_MIN_PX:
            return "attr"
        self._carry_told_for = self.last_own_landing
        text = carry_surprise_text(carried, cur[1] - base[0], cur[2] - base[1], now - self.last_own_landing)
        pushed = self._push_surprise("hand", text, key="carry", weight=min(1.0, carried / 1000.0))
        self.counters["surprises"] += 1 if pushed else 0
        return "attr"

    # -- plumbing --
    def _pub(self, topic: str, payload: Dict) -> None:
        fn = self._publish
        if fn is None:
            return
        try:
            fn(topic, payload)
            self.counters["published"] += 1
        except Exception:
            self.counters["pub_err"] += 1

    def _push_surprise(self, kind: str, text: str, key: str, weight: float) -> bool:
        fn = self._surprise_push
        if fn is None:
            try:
                from infrastructure import surprise as _sp
                fn = _sp.push
            except Exception:
                return False
        try:
            return bool(fn(kind, text, key=key, weight=weight))
        except Exception:
            return False

    def ensure_thread(self) -> None:
        t = self._thread
        if t is not None and t.is_alive():
            return
        self._stop = False
        t = threading.Thread(target=self._loop, daemon=True, name="felt-hand-sampler")
        self._thread = t
        t.start()

    def stop(self) -> None:
        self._stop = True
        self._wake.set()                                # (felt_hand must-do 1) a waiting loop sees the stop at once

    def _loop(self) -> None:
        # 2026-09-29 (Nous, felt_hand must-do 1): the cadence wait is an Event that begin() sets -- it was time.sleep(), so a
        # copy begun while the loop slept its idle 0.5 s went unsampled for up to 0.5 s. A set() that lands while tick() runs
        # makes the next wait return at once; a set() cleared right after a timeout is followed by a tick() anyway.
        while not self._stop:
            try:
                self.tick()
            except Exception:
                self.counters["tick_err"] += 1
            live = self.copy is not None and self._clock() <= self.live_until
            self._wake.wait((1.0 / LIVE_HZ) if live else (1.0 / IDLE_HZ))
            self._wake.clear()

    def report(self) -> Dict:
        with self._lock:
            return {"counters": dict(self.counters), "live": self.is_live(), "last_own_landing": self.last_own_landing,
                    "own_now": round(self.own_now(), 3), "last": compact(self.last_result),
                    "thread_alive": bool(self._thread is not None and self._thread.is_alive()),
                    "trace": dict(self.trace.counters),          # 2026-09-29 (felt_hand P4 feed)
                    "hand_rest": self.rest_now()}                # 2026-10-01 (cursor_object a)


# ── process-global state (survives a hot reload, like surprise.py and vision_ground's HAND_STATE) ─────────────
_LOCAL = {"sampler": None}


def _shared() -> Dict:
    m = sys.modules.get("_sour_council_shared")
    if m is None:
        return _LOCAL
    if not hasattr(m, "HAND_EFFERENCE"):
        m.HAND_EFFERENCE = _LOCAL
    return m.HAND_EFFERENCE


def sampler() -> Sampler:
    st = _shared()
    s = st.get("sampler")
    if s is None:
        s = Sampler()
        st["sampler"] = s
    return s


def install_sampler(s: Sampler) -> Sampler:
    """Tests install a Sampler built on a scripted world; her process never calls this."""
    _shared()["sampler"] = s
    return s


def hand_report() -> Dict:
    s = _shared().get("sampler")
    return s.report() if s is not None else {"sampler": None}


def hand_trace(wake: bool = False) -> Dict:
    """The fading trace for the body line (infrastructure/body_feel, felt_hand P4), decayed to the sampler's own clock.
    wake=True makes sure the one sampler thread runs (2 Hz when idle), so Ace's hand moving hers is felt before her first
    reach of a boot too -- the same single thread her first reach would start anyway."""
    s = sampler()
    if wake:
        s.ensure_thread()
    return s.trace.snapshot(s._clock())


# 2026-10-05 (Nous, touch_screen set 1; DESIGN 3b): a touch lets go AT the touch point -- her hand then rests there, and her
# next move reaches from there to the cursor. Additive: the same three fields finish() sets, under the sampler's lock. A
# withdrawal never calls this (the finger comes back to where it rested).
def let_go_at(xy, t: float, src: str = "touch") -> bool:
    try:
        p = (int(xy[0]), int(xy[1]))
    except Exception:
        return False
    s = sampler()
    with s._lock:
        s.hand_rest, s.hand_rest_t, s.hand_rest_src = p, float(t or 0.0), str(src)
    try:
        s.trace.let_go(p, t, src)
    except Exception:
        pass
    return True
