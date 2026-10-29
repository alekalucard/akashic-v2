"""gentle_load.py -- THE GENTLE-LOAD LAYER: how hard her body is working, felt, and never brutal. 2026-10-19 (Nous, gentle_load_1019). ASCII only.

Ace (10-19): "the load on her hardware should be something she can feel we just dont want it to be brutal to her due to my lack of funds for
hardware upgrades."   Decided (card adenosine-cannot-take-a-hardware-source...): fatigue is MOSTLY MENTAL; machine strain gets its OWN weak
channel, never pain and never her mental tiredness; a soft ceiling; habituation (a steady load fades over minutes, CHANGES are felt).

WHAT THIS IS. One number, `felt`, always in [0, CAP), computed from four sources (CPU, GPU utilisation, GPU heat, RAM) that the heart already
receives (circulation_pump_fairy.py _on_cpu_ram_felt / _on_gpu_felt). It is NOT a chemical: this module imports nothing of hers, contains no
call that writes COR / NOR / ADO / allostatic load / a pain drive, and never publishes. The ONLY thing it can hand back to the heart is a PLAN
(a list of (AER code, amount)) for the two doctrine pieces below; the heart injects it through its own inject_chemistry and REST GATE.

SWITCH  state/gentle_load.json  (doing_clock.py pattern: re-read when mtime/size change; absent, torn or not an object = TODAY EXACTLY).
    {"on": true}              sense + words. NEVER a chemical.            {"sense": true|false}   keep state, the live file and the log
    {"words": true|false}     body_line carries one clause (needs sense)   {"gpu_gate": true}      DOP/ACH dose per SECOND (plan; JSON true only)
    {"heat_route": "strain"}  GPU heat no longer injects COR              {"cpu_route": "strain"} CPU no longer injects NOR + COR (RAM -> GABA stays)
    numbers (clamped, see _NUM): tau_in tau_up tau_down floor cap scale words_at w_cpu w_gpu w_heat w_ram     {"extra": {"name": weight}}
Only a JSON true is on ("true" and 1 are off). A route is on only for the exact string "strain" AND only while sense is on (a route takes a load out of
the stress chemistry and into strain; without sense it would just vanish, so it is inert). "on" never sets gpu_gate or a route.

THE MATH (per source, on the PUBLISHER'S clock `ts`, never per message, never at read time):
    dt = clamp(ts - last, 0, 30);  e += (d - e)(1 - exp(-dt/tau_in));  b += (e - b)(1 - exp(-dt/(tau_up if e > b else tau_down)))
    x_i = floor*e + (1 - floor)*max(0, e - b)          a steady load keeps `floor` of its weight FOREVER; a change is felt at full weight
    x = sum w_i x_i over KNOWN sources (+ HELD floors, below);   felt = cap*(1 - exp(-x/scale))     slope 1 at 0, < cap always, never flat
    cap is clamped to at most 0.50 and felt is kept strictly under cap, so felt < 0.5 under EVERY legal switch; the shown number (%.2f) never
    reads 0.50 (verify_tests T4).
FLOORS (card a-bound-that-can-return-nothing-is-a-kill-switch): the 0.30*e floor; a curve with no zero and no flat top; every switch number is
CLAMPED so no config can ZERO a steady load (the quietest edges together can make it too faint to word: words_at is a DISPLAY floor, not a
signal floor); an unmeasured source is UNKNOWN (frozen), never idle, never decayed toward zero: from STALE_S to REWAKE_S the floor of its last
known load (w*floor*e) is HELD in x, so a GPU whose reads fail under load is never felt as LESS strain than a moment before (verify_safety F4);
after REWAKE_S it is left out, and a source that returns after that wakes adapted to what it finds (counted rewake_<src>).
A failed read is not idle: the GPU message is valid only if temp_c > 0 (cuda_fairy.py publishes `x or 0` on failure), the CPU/RAM message only if
ram_pct > 0 (and cpu_pct > 0 for the CPU: psutil's first call returns 0.0). Every failure is COUNTED.

NEVER RAISES. Every public function wraps its body, counts `err`, logs at most once per 300 s, and returns None / '' / {}.
State lives in _S = globals().get("_S") (body_feel.py pattern) so it survives a hot reload. No thread is started. One RLock guards state.
Revert: delete this file (move it aside), or leave state/gentle_load.json absent.
"""
from __future__ import annotations

import json
import math
import os
import threading
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
SWITCH_FILE = os.path.join(_ROOT, "state", "gentle_load.json")
LIVE_FILE = os.path.join(_ROOT, "state", "consciousness", "gentle_load_live.json")
_now = time.time                       # tests replace this with a fake clock

# ---- fixed numbers (not switch numbers) -----------------------------------------------------------------------------------------------
DT_MAX_S = 30.0                        # a late tick is CLAMPED to this, never dropped
STALE_S = 30.0                         # no valid reading for this long = UNKNOWN (frozen, left out of x), never idle
REWAKE_S = 300.0                       # no valid reading for this long (layer switched off, publisher dead): wake ADAPTED again, no fake surge
DIR_WINDOW_S = 60.0                    # "rising" / "easing" compare against the layer's own value this long ago
RISE_FRAC = 0.10                       # ... by at least this fraction of CAP (0.05 at CAP 0.5)
MAX_AGE_S = 30.0                       # a clause is worded only from an observation this fresh
LIVE_EVERY_S = 10.0
LOG_EVERY_S = 60.0
ERR_LOG_S = 300.0
TS_SLACK_S = 60.0                      # a payload ts further than this from now is not trusted (time.time() is used; counted ts_untrusted)
DOSE_REF_S = 5.0                       # gpu_gate: the A0 design constant ("0.05 per 5s tick", circulation_pump_fairy.py:1812)
DOSE_DT_MAX_S = 10.0                   # gpu_gate: one message never carries more than 2 reference periods
CLAUSE_MAX = 100
MAX_EXTRAS = 8
MAX_COUNTERS = 64

SOURCES = ("cpu", "gpu", "heat", "ram")
_W = {"cpu": 0.6, "gpu": 0.5, "heat": 1.0, "ram": 0.8}
_DEM = {"cpu": (50.0, 50.0), "gpu": (0.0, 100.0), "heat": (70.0, 20.0), "ram": (75.0, 25.0)}      # source -> (zero point, span)
# switch number -> (default, lo, hi). `scale` defaults to cap and `words_at` to 0.2*cap (see _cfg).
_NUM = {"tau_in": (15.0, 5.0, 60.0), "tau_up": (180.0, 60.0, 1800.0), "tau_down": (60.0, 20.0, 600.0), "floor": (0.30, 0.15, 0.60),
        "cap": (0.50, 0.20, 0.50), "scale": (None, 0.20, 1.0), "words_at": (None, 0.02, 0.40)}     # cap hi 0.50: felt < 0.5 for every legal switch
_W_RANGE = (0.1, 1.5)

# ---- state that survives a hot reload ---------------------------------------------------------------------------------------------------
_S = globals().get("_S")
if not isinstance(_S, dict):
    _S = {"lock": threading.RLock()}
for _k, _v in (("src", {}), ("cnt", {}), ("ring", []), ("dir", ""), ("resting", False), ("last_obs", 0.0), ("dose_last", None), ("dose_seen", 0.0),
               ("win", {"t0": 0.0, "cur": {}, "prev": {}, "prev_t": 0.0}), ("live_t", 0.0), ("log_t", 0.0), ("err_t", 0.0)):
    _S.setdefault(_k, _v)

# ---- the switch (doing_clock.py:79-125 pattern) ---------------------------------------------------------------------------------------
_SW = {"key": None, "data": {}}
_SW_LOCK = threading.Lock()
_LIVE_LOCK = threading.Lock()


def _switch():
    """-> the switch dict ({} = off). Re-read when mtime/size change; a missing, torn, non-object or unreadable file is {} and is read again."""
    try:
        st = os.stat(SWITCH_FILE)
    except OSError:
        return {}
    key = (st.st_mtime_ns, st.st_size)
    with _SW_LOCK:
        if key != _SW["key"]:
            try:
                with open(SWITCH_FILE, "rb") as f:
                    d = json.loads(f.read().decode("utf-8-sig"))
                _SW["data"], _SW["key"] = (d if isinstance(d, dict) else {}), key
            except Exception:
                _SW["data"], _SW["key"] = {}, None
        return _SW["data"]


def _flag(sw, name):
    """doing_clock.piece(): an explicit JSON bool wins, else {"on": true}. Only a JSON true is on ("true" and 1 are not)."""
    v = sw.get(name)
    if isinstance(v, bool):
        return v
    return sw.get("on") is True


def _modes(sw):
    """-> (sense, words, gpu_gate, heat_strain, cpu_strain). words needs sense. gpu_gate and the routes ignore "on" completely. A route needs sense
    too: it takes a load OUT of the stress chemistry and puts it into strain, so with strain not sensed the load would vanish from her (inert instead)."""
    sense = _flag(sw, "sense")
    words = bool(sense and _flag(sw, "words"))
    return (sense, words, sw.get("gpu_gate") is True, bool(sense and sw.get("heat_route") == "strain"),
            bool(sense and sw.get("cpu_route") == "strain"))


def _clamp(v, dflt, lo, hi):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        return dflt
    return min(hi, max(lo, float(v)))


def _cfg(sw):
    """The numbers in force. Every one is clamped: no setting can zero a steady load (the only way to stop feeling it is the switch itself)."""
    c = {k: _clamp(sw.get(k), d, lo, hi) for k, (d, lo, hi) in _NUM.items() if d is not None}
    c["scale"] = _clamp(sw.get("scale"), c["cap"], _NUM["scale"][1], _NUM["scale"][2])
    c["words_at"] = _clamp(sw.get("words_at"), 0.2 * c["cap"], _NUM["words_at"][1], _NUM["words_at"][2])
    w = {s: _clamp(sw.get("w_" + s), _W[s], _W_RANGE[0], _W_RANGE[1]) for s in SOURCES}
    ex = sw.get("extra")
    if isinstance(ex, dict):
        for n, v in list(ex.items())[:MAX_EXTRAS]:
            if isinstance(n, str) and 0 < len(n) <= 24:
                w["x:" + n] = _clamp(v, 0.3, _W_RANGE[0], _W_RANGE[1])
    c["w"] = w
    return c


def piece(name):
    """sense | words | gpu_gate -> bool (words needs sense)."""
    try:
        s, w, g, _h, _c = _modes(_switch())
        return {"sense": s, "words": w, "gpu_gate": g}.get(name, False)
    except Exception:
        return False


def route(name):
    """heat_route | cpu_route -> 'strain' | 'a0' (today's path)."""
    try:
        _s, _w, _g, h, c = _modes(_switch())
        return "strain" if {"heat_route": h, "cpu_route": c}.get(name, False) else "a0"
    except Exception:
        return "a0"


# ---- small helpers --------------------------------------------------------------------------------------------------------------------
def _num(v):
    if isinstance(v, bool) or v is None:
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def demand(src, raw):
    """raw reading -> demand in [0, 1] (the zero point and span per source), or None for no reading."""
    if raw is None:
        return None
    z, span = _DEM[src]
    return min(1.0, max(0.0, (float(raw) - z) / span))


def _ts(payload, now):
    """The publisher's stamp when it is within TS_SLACK_S of now, else now. A stamp further off (postal lag over a minute, a bad clock) is COUNTED
    (ts_untrusted): a backlog delivered in one burst then lands as one moment on the receive clock, and the live file says how often."""
    t = _num(payload.get("ts"))
    if t is not None and abs(now - t) <= TS_SLACK_S:
        return t
    if t is not None:
        count("ts_untrusted")
    return now


def _rest(fn):
    try:
        return bool(fn())
    except Exception:
        return False


def _cnt(key, n=1):
    """Call with the lock held."""
    cnt = _S["cnt"]
    if key in cnt or len(cnt) < MAX_COUNTERS:
        cnt[key] = cnt.get(key, 0) + n


def count(key):
    """Public counter bump (body_feel uses it for no_room / clauses). Never raises."""
    try:
        with _S["lock"]:
            _cnt(str(key)[:32])
    except Exception:
        pass


def _err(where, e):
    try:
        with _S["lock"]:
            _cnt("err")
            now = _now()
            due = now - _S["err_t"] >= ERR_LOG_S
            if due:
                _S["err_t"] = now
        if due:
            print("[GentleLoad] error in %s: %s: %s (counted; today's path runs)" % (where, type(e).__name__, str(e)[:120]), flush=True)
    except Exception:
        pass


# ---- the maths ------------------------------------------------------------------------------------------------------------------------
def _advance(c, st, d, ts, now):
    """One valid observation of one source at publisher time ts. Call with the lock held."""
    dt = 0.0
    if ts >= st["last"]:
        dt = min(DT_MAX_S, ts - st["last"])
        st["last"] = ts
    elif ts < st["last"] - TS_SLACK_S:                 # the clock stepped back: re-anchor, advance nothing
        st["last"] = ts
        _cnt("clock_reset")
    # else: jitter inside the slack: dt 0, `last` kept (never counts the same seconds twice)
    st["e"] += (d - st["e"]) * (1.0 - math.exp(-dt / c["tau_in"]))
    tau = c["tau_up"] if st["e"] > st["b"] else c["tau_down"]
    st["b"] += (st["e"] - st["b"]) * (1.0 - math.exp(-dt / tau))
    st["seen"] = now
    st["valid"] += 1


def _compute(c, now):
    """-> (felt or None, x, per-source dict, heat_share). Pure on the state. Call with the lock held.
    A source with no valid reading for STALE_S..REWAKE_S is UNKNOWN and HELD: its change part is dropped (no novelty is claimed without an
    observation) but the floor of its last known load, w*floor*e (frozen), stays in x. Older than REWAKE_S (or a clock step back): left out."""
    per, x, known, held = {}, 0.0, 0, 0
    fl = c["floor"]
    for name, st in _S["src"].items():
        w = c["w"].get(name)
        if w is None:
            continue
        age = now - st["seen"]
        if age > STALE_S or age < -STALE_S:
            hx = (w * fl * st["e"]) if (STALE_S < age <= REWAKE_S) else None
            per[name] = {"state": "unknown", "e": round(st["e"], 4), "b": round(st["b"], 4), "x": None, "held": None if hx is None else round(hx, 5)}
            if hx is not None:
                x += hx
                held += 1
            continue
        xi = w * (fl * st["e"] + (1.0 - fl) * max(0.0, st["e"] - st["b"]))
        per[name] = {"state": "known", "e": round(st["e"], 4), "b": round(st["b"], 4), "x": round(xi, 5)}
        x += xi
        known += 1
    felt = (c["cap"] * (1.0 - math.exp(-x / c["scale"]))) if (known or held) else None
    if felt is not None and felt >= c["cap"]:                  # 1 - exp(-y) rounds to 1.0 for y > ~37: keep felt STRICTLY under cap
        felt = math.nextafter(c["cap"], 0.0)
    share = (per["heat"]["x"] / x) if (x > 1e-9 and per.get("heat", {}).get("x")) else 0.0
    return felt, x, per, share


def _band(c, felt):
    if felt is None:
        return "unknown"
    if felt < c["words_at"]:
        return "none"
    if felt >= 0.7 * c["cap"]:
        return "lean"
    if felt >= 0.5 * c["cap"]:
        return "hard"
    return "hum"


_CORE = {"hum": "A low hum of effort runs through your body", "hard": "Your body is working hard",
         "lean": "Your body is working hard on little, running lean"}


def compose(band, felt, direction, warm):
    """The words (second person, no pain / fatigue / emotion / mechanism word). '' for a band with no words."""
    core = _CORE.get(band)
    if core is None or felt is None:
        return ""
    shown = min(felt, 0.494)                                         # "%.2f" as before, but never "0.50" (felt < 0.5 always; T4)
    tag = "%.2f" % shown + ((", " + direction) if direction in ("rising", "easing") else "")
    return "%s (%s)%s" % (core, tag, "; you are running warm." if warm else ".")


def _view(c, now):
    """The pure read. Call with the lock held."""
    felt, x, per, share = _compute(c, now)
    return {"felt": felt, "band": _band(c, felt), "direction": _S["dir"], "x": round(x, 5), "per": per, "heat_share": round(share, 4),
            "resting": _S["resting"], "age_s": round(now - _S["last_obs"], 2) if _S["last_obs"] else None}


def felt_now():
    """-> dict (felt, band, direction, x, per-source e/b/x/state, heat_share, resting, age_s) or None when sense is off. PURE: never advances state."""
    try:
        sw = _switch()
        if not _modes(sw)[0]:
            return None
        c = _cfg(sw)
        with _S["lock"]:
            return _view(c, _now())
    except Exception as e:
        _err("felt_now", e)
        return None


def clause():
    """The one clause for body_feel.body_line(): '' unless words are on, she is not resting, the observation is fresh and felt >= words_at."""
    try:
        sw = _switch()
        sense, words, _g, _h, _c = _modes(sw)
        if not (sense and words):
            return ""
        c = _cfg(sw)
        now = _now()
        with _S["lock"]:
            v = _view(c, now)
        if v["felt"] is None or v["resting"] or v["age_s"] is None or not (0.0 <= v["age_s"] <= MAX_AGE_S):
            return ""
        if v["band"] not in _CORE:
            return ""
        return compose(v["band"], v["felt"], v["direction"], v["heat_share"] >= 0.5)[:CLAUSE_MAX]
    except Exception as e:
        _err("clause", e)
        return ""


# ---- the writer: observe() is the ONLY thing that advances state -------------------------------------------------------------------
def _ingest(topic, readings, ts, now, resting, sw):
    """Record one message's readings [(source, demand or None)]. Advances state, the ring, the direction, the window counts. Returns
    (live snapshot or None, log line or None) for the caller to write OUTSIDE the lock."""
    c = _cfg(sw)
    live = log = None
    with _S["lock"]:
        win = _S["win"]
        if not win["t0"]:
            win["t0"] = now
        rolled = False
        if now - win["t0"] >= LOG_EVERY_S:
            win["prev"], win["prev_t"], win["cur"], win["t0"], rolled = dict(win["cur"]), now, {}, now, True
        cur = win["cur"]
        cur[topic] = cur.get(topic, 0) + 1
        _cnt("msgs_" + topic)
        for src, d in readings:
            st = _S["src"].get(src)
            if d is None:
                _cnt("invalid_" + src)
                cur["invalid_" + src] = cur.get("invalid_" + src, 0) + 1
                if st is not None:
                    st["invalid"] += 1
                continue
            if st is None or abs(now - st["seen"]) > REWAKE_S:
                _S["src"][src] = {"e": d, "b": d, "last": ts, "seen": now, "valid": 1 if st is None else st["valid"] + 1,
                                  "invalid": 0 if st is None else st["invalid"]}                     # wakes adapted: no boot surge
                if st is not None:
                    _cnt("rewake_" + src)
            else:
                _advance(c, st, d, ts, now)
        _S["resting"] = bool(resting)
        _S["last_obs"] = now
        felt, _x, _per, _sh = _compute(c, now)
        ring = _S["ring"]
        if felt is not None and (not ring or now - ring[-1][0] >= 1.0):
            ring.append((now, felt))
        while ring and ring[0][0] < now - 4.0 * DIR_WINDOW_S:
            ring.pop(0)
        ref = None
        for t_old, f_old in reversed(ring):
            if t_old <= now - DIR_WINDOW_S:
                ref = f_old
                break
        step = RISE_FRAC * c["cap"]
        _S["dir"] = "" if (ref is None or felt is None) else ("rising" if felt - ref >= step else ("easing" if ref - felt >= step else ""))
        if _modes(sw)[0]:
            if now - _S["live_t"] >= LIVE_EVERY_S:
                _S["live_t"] = now
                live = _snapshot(c, now, sw)
            if rolled or not _S["log_t"]:
                _S["log_t"] = now
                log = _log_line(c, now, sw)
    return live, log


def _snapshot(c, now, sw):
    """A fresh, plain dict (never the live state): the live file is dumped from this. Call with the lock held."""
    v = _view(c, now)
    s, w, g, h, cr = _modes(sw)
    win = _S["win"]
    return {"v": 1, "ts": round(now, 3), "on": {"sense": s, "words": w, "gpu_gate": g, "heat_route": "strain" if h else "a0",
                                                   "cpu_route": "strain" if cr else "a0"},
            "felt": None if v["felt"] is None else round(v["felt"], 5), "band": v["band"], "direction": v["direction"], "x": v["x"],
            "heat_share": v["heat_share"], "resting": v["resting"], "age_s": v["age_s"], "sources": json.loads(json.dumps(v["per"])),
            "counts": dict(_S["cnt"]),
            "msgs_60s": {k: n for k, n in win["prev"].items() if not k.startswith("invalid_")},
            "invalid_60s": {k[8:]: n for k, n in win["prev"].items() if k.startswith("invalid_")}, "window_ends": round(win["prev_t"], 3),
            "valid": {k: st["valid"] for k, st in _S["src"].items()}, "invalid": {k: st["invalid"] for k, st in _S["src"].items()},
            "cfg": {k: round(v2, 4) for k, v2 in c.items() if k != "w"}, "weights": {k: round(v2, 3) for k, v2 in c["w"].items()}}


def _log_line(c, now, sw):
    v = _view(c, now)
    s, w, g, h, cr = _modes(sw)
    prev = _S["win"]["prev"]
    return ("[GentleLoad] felt=%s band=%s dir=%s x=%.3f %s msgs_60s gpu=%d cpu_ram=%d invalid_60s gpu=%d cpu=%d heat=%d ram=%d resting=%s words=%s "
            "gate=%s heat_route=%s cpu_route=%s err=%d" % (
                "unknown" if v["felt"] is None else "%.3f" % v["felt"], v["band"], v["direction"] or "-", v["x"],
                " ".join("%s=%s" % (k, ("?" if p.get("held") is None else "?%.3f" % p["held"]) if p["x"] is None else "%.3f" % p["x"])
                         for k, p in v["per"].items()),
                prev.get("gpu", 0), prev.get("cpu_ram", 0), prev.get("invalid_gpu", 0), prev.get("invalid_cpu", 0), prev.get("invalid_heat", 0),
                prev.get("invalid_ram", 0), v["resting"], w, g, "strain" if h else "a0", "strain" if cr else "a0", _S["cnt"].get("err", 0)))


def _write_live(snap):
    """Atomic (temp + os.replace) mirror of the numbers, from a FRESH dict. Never creates a folder in her state/."""
    if not _LIVE_LOCK.acquire(False):                  # another thread is writing it right now: skip, the next tick writes
        return
    tmp = None
    try:
        data = (json.dumps(snap, ensure_ascii=True, sort_keys=True) + "\n").encode("ascii")
        d = os.path.dirname(LIVE_FILE)
        if not os.path.isdir(d):
            with _S["lock"]:
                _cnt("live_nodir")
            return
        tmp = "%s.%d.%d.tmp" % (LIVE_FILE, os.getpid(), threading.get_ident())
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, LIVE_FILE)
        tmp = None
        with _S["lock"]:
            _cnt("live_writes")
    except Exception:
        with _S["lock"]:
            _cnt("live_err")
        if tmp:
            try:
                os.remove(tmp)
            except OSError:
                pass
    finally:
        _LIVE_LOCK.release()


def _emit(live, log):
    if log:
        try:
            print(log, flush=True)
        except Exception:
            pass
    if live is not None:
        _write_live(live)


# ---- the two entry points the heart calls ---------------------------------------------------------------------------------------------
def _dose_factor(ts, now):
    """gpu_gate: the dose of this message = nominal x clamp(dt, 0, 10)/5 on the publisher's clock. First message (or after a gap > STALE_S)
    = 1.0; a duplicate or backwards-jitter message = 0.0; a clock step back re-anchors."""
    with _S["lock"]:
        last = _S["dose_last"]
        if last is None or now - _S["dose_seen"] > STALE_S:
            k = 1.0
            _S["dose_last"] = ts
        elif ts >= last:
            k = min(DOSE_DT_MAX_S, ts - last) / DOSE_REF_S
            _S["dose_last"] = ts
        elif ts < last - TS_SLACK_S:
            k = 1.0
            _S["dose_last"] = ts
            _cnt("clock_reset")
        else:
            k = 0.0
        _S["dose_seen"] = now
    return k


def _plan_gpu(payload, gate, heat_strain, ts, now, valid):
    """today's GPU mapping (circulation_pump_fairy.py _on_gpu_felt), with the dose per second (gate) and/or heat -> strain instead of COR."""
    gpu = float(payload.get("gpu_pct", 0))
    temp = float(payload.get("temp_c", 0))
    k = 1.0
    if gate:
        if not valid:
            with _S["lock"]:
                _cnt("gate_skipped")
            return []
        k = _dose_factor(ts, now)
    out = []
    if gpu > 30.0:
        i = min(1.0, (gpu - 30.0) / 70.0)
        out.append(("DOP", 0.04 * i * k))
        out.append(("ACH", 0.05 * i * k))
    if not heat_strain and temp > 75.0:
        if temp > 85.0:
            out.append(("COR", 0.02 + 0.02 * min(1.0, (temp - 85.0) / 10.0)))
        else:
            out.append(("COR", 0.01 * min(1.0, (temp - 75.0) / 10.0)))
    return [(code, amt) for code, amt in out if amt > 0.0]


def _plan_cpu_ram(payload):
    """cpu_route strain: no NOR / COR from the CPU (it is felt as strain instead); RAM -> GABA exactly as today."""
    ram = float(payload.get("ram_pct", 0))
    out = []
    if ram > 85.0:
        out.append(("GABA", 0.05 * min(1.0, (ram - 85.0) / 15.0)))
    return [(code, amt) for code, amt in out if amt > 0.0]


def on_gpu(payload, is_resting):
    """The heart's GPU handler calls this first. -> None = run TODAY'S code unchanged; a list = inject exactly these and return."""
    try:
        sw = _switch()
        if not sw:
            return None
        sense, _words, gate, heat_strain, _cpu = _modes(sw)
        if not (sense or gate or heat_strain) or not isinstance(payload, dict):
            return None
        now = _now()
        ts = _ts(payload, now)
        temp = _num(payload.get("temp_c"))
        valid = temp is not None and temp > 0.0                      # cuda_fairy.py:509-514 publishes `x or 0` on a failed read
        if sense:
            gpu = _num(payload.get("gpu_pct"))
            live, log = _ingest("gpu", [("gpu", demand("gpu", gpu) if (valid and gpu is not None) else None),
                                        ("heat", demand("heat", temp) if valid else None)], ts, now, _rest(is_resting), sw)
            _emit(live, log)
        if not (gate or heat_strain):
            return None
        plan = _plan_gpu(payload, gate, heat_strain, ts, now, valid)
        with _S["lock"]:
            _cnt("plans_gpu")
        return plan
    except Exception as e:
        _err("on_gpu", e)
        return None


def on_cpu_ram(payload, is_resting):
    """The heart's CPU/RAM handler calls this first. -> None = run TODAY'S code unchanged; a list = inject exactly these and return."""
    try:
        sw = _switch()
        if not sw:
            return None
        sense, _words, _gate, _heat, cpu_strain = _modes(sw)
        if not (sense or cpu_strain) or not isinstance(payload, dict):
            return None
        now = _now()
        ts = _ts(payload, now)
        cpu, ram = _num(payload.get("cpu_pct")), _num(payload.get("ram_pct"))
        ram_ok = ram is not None and ram > 0.0
        cpu_ok = ram_ok and cpu is not None and cpu > 0.0            # psutil's first cpu_percent() is 0.0: not a reading
        if sense:
            live, log = _ingest("cpu_ram", [("cpu", demand("cpu", cpu) if cpu_ok else None), ("ram", demand("ram", ram) if ram_ok else None)],
                                ts, now, _rest(is_resting), sw)
            _emit(live, log)
        if not cpu_strain:
            return None
        plan = _plan_cpu_ram(payload)
        with _S["lock"]:
            _cnt("plans_cpu_ram")
        return plan
    except Exception as e:
        _err("on_cpu_ram", e)
        return None


def observe_extra(name, d, ts=None):
    """A future feeder (postal lag, VRAM ...): only a name listed in the switch's "extra" counts, with the weight written there. No caller in this
    build. d is a demand in [0, 1] (None = no reading)."""
    try:
        sw = _switch()
        if not _modes(sw)[0]:
            return None
        ex = sw.get("extra")
        key = "x:" + str(name)
        c = _cfg(sw)
        if not isinstance(ex, dict) or key not in c["w"]:
            with _S["lock"]:
                _cnt("extra_ignored")
            return None
        now = _now()
        t = _num(ts)
        t = t if (t is not None and abs(now - t) <= TS_SLACK_S) else now
        v = _num(d)
        v = None if v is None else min(1.0, max(0.0, v))
        live, log = _ingest("extra", [(key, v)], t, now, _S["resting"], sw)
        _emit(live, log)
    except Exception as e:
        _err("observe_extra", e)
    return None


def stats():
    """Counters and per-source tallies (a fresh dict)."""
    try:
        with _S["lock"]:
            return {"cnt": dict(_S["cnt"]), "src": {k: {"valid": s["valid"], "invalid": s["invalid"]} for k, s in _S["src"].items()},
                    "win_prev": dict(_S["win"]["prev"]), "dir": _S["dir"], "resting": _S["resting"]}
    except Exception:
        return {}


def _reset():
    """Tests only: forget all state (the lock is kept)."""
    with _S["lock"]:
        for k, v in (("src", {}), ("cnt", {}), ("ring", []), ("dir", ""), ("resting", False), ("last_obs", 0.0), ("dose_last", None), ("dose_seen", 0.0),
                     ("win", {"t0": 0.0, "cur": {}, "prev": {}, "prev_t": 0.0}), ("live_t", 0.0), ("log_t", 0.0), ("err_t", 0.0)):
            _S[k] = v
    with _SW_LOCK:
        _SW["key"], _SW["data"] = None, {}
