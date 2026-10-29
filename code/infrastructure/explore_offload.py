"""explore_offload.py -- XO (engines E2a, step 14b, 2026-10-14 Nous): the cortex's autonomous explore comes off the tick thread.

WHY (DESIGN_14b.md 2 + 3.3, MEASURED): CortexEngine.tick() runs _autonomous_explore inline every 15th tick (a full react(), its
own 6 s deadline). The serial cortex is the ONLY fairy that drops heartbeat ticks because its exec thread is busy (Boot N 2,301,
Boot M 3,501), and explores take an estimated 44% of a tick thread (145/h x ~11 s, INFERRED).

WHAT THIS DOES: cortex_engine.py's tick() calls submit(engine, now, energy) where it used to call the explore. submit hands the
explore to ONE daemon worker thread ("CortexExplore") and returns at once. At most ONE explore is in flight: a submit while one
is running returns True and is counted as "skipped" (that is the limiter). The explore itself is unchanged (same method, same
candidate choice under engine._lock, same _last_explore_time / _total_autonomous_explores bookkeeping).

THE SWITCH: state/explore_offload.json {"on": true, "stuck_s": 120}, re-read whenever its (mtime_ns, size) changes (the 10a rule,
cortex_engine.py _reason_drop_cfg), so it can be flipped while she runs. "stuck_s" is clamped to 30..600 (default 120; a value
that is not a finite number = the default, never "off"). A missing file, a file that does not parse (a BOM included), "on"
anything but JSON true, or any error = submit returns False = tick() runs the explore inline exactly as today.

THE FLOOR (card a-bound-that-can-return-nothing-is-a-kill-switch): submit returns False -- and today's synchronous call runs --
whenever the in-flight explore is older than stuck_s, the worker thread is dead, or a worker cannot be started. So the offload can
never yield fewer explore attempts than today's path. An exception inside an explore clears "busy" (finally).
Lines (ASCII): "[CortexEngine] EXPLORE-OFFLOAD armed ..." / "... disarmed ..." on each change of the switch, and
"[CortexEngine] EXPLORE-OFFLOAD done=... skipped=... fallback=... err=... avg_ms=... max_ms=..." every 50 completions.
Stdlib only. Never raises.
"""
import json
import math
import os
import threading
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SWITCH_FILE = os.path.join(_ROOT, "state", "explore_offload.json")
STUCK_DEFAULT_S = 120.0
STUCK_MIN_S = 30.0
STUCK_MAX_S = 600.0
REPORT_EVERY = 50
THREAD_NAME = "CortexExplore"

_LOCK = threading.Lock()
_CACHE = (None, None)          # (file key, cfg); replaced whole
_EVENT = threading.Event()
_ST = {"sig": None, "busy_since": 0.0, "slot": None, "thread": None,
       "done": 0, "skipped": 0, "fallback": 0, "err": 0, "sum_ms": 0.0, "max_ms": 0.0}
_clock = time.time              # test seam


def _say(msg):
    try:
        print(str(msg).encode("ascii", "replace").decode("ascii"), flush=True)
    except Exception:
        pass


def _stuck(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return STUCK_DEFAULT_S
    v = float(v)
    if not math.isfinite(v):
        return STUCK_DEFAULT_S
    return min(STUCK_MAX_S, max(STUCK_MIN_S, v))


def cfg():
    """{"stuck_s": float} when ON, else None. Re-read when the file changes. Never raises."""
    global _CACHE
    try:
        st = os.stat(SWITCH_FILE)
    except OSError:
        return None
    try:
        key = (st.st_mtime_ns, st.st_size)
        k, c = _CACHE
        if key == k:
            return c
        try:
            with open(SWITCH_FILE, "rb") as f:
                d = json.loads(f.read().decode("utf-8"))
        except Exception:
            _CACHE = (None, None)        # torn or bad: today's path now, read again next time
            return None
        c = None
        if isinstance(d, dict) and d.get("on") is True:
            c = {"stuck_s": _stuck(d.get("stuck_s", STUCK_DEFAULT_S))}
        _CACHE = (key, c)
        return c
    except Exception:
        return None


def _arm_note(c):
    sig = None if c is None else c["stuck_s"]
    msg = None
    with _LOCK:
        if sig != _ST["sig"]:
            if sig is not None:
                msg = ("[CortexEngine] EXPLORE-OFFLOAD armed stuck_s=%.0f (explore runs on thread %s, one in flight; "
                       "stuck / dead worker = inline as today)" % (sig, THREAD_NAME))
            else:
                msg = ("[CortexEngine] EXPLORE-OFFLOAD disarmed done=%d skipped=%d fallback=%d err=%d (inline as today)"
                       % (_ST["done"], _ST["skipped"], _ST["fallback"], _ST["err"]))
            _ST["sig"] = sig
    if msg:
        _say(msg)


def _worker():
    while True:
        _EVENT.wait()
        with _LOCK:
            _EVENT.clear()
            job = _ST["slot"]
            _ST["slot"] = None
        if job is None:
            continue
        engine, now, energy = job
        t0 = time.perf_counter()
        ok = True
        report = None
        try:
            engine._autonomous_explore(now, energy)
        except Exception:
            ok = False
        finally:
            ms = (time.perf_counter() - t0) * 1000.0
            with _LOCK:
                _ST["busy_since"] = 0.0
                _ST["done"] += 1
                if not ok:
                    _ST["err"] += 1
                _ST["sum_ms"] += ms
                if ms > _ST["max_ms"]:
                    _ST["max_ms"] = ms
                if _ST["done"] % REPORT_EVERY == 0:
                    report = ("[CortexEngine] EXPLORE-OFFLOAD done=%d skipped=%d fallback=%d err=%d avg_ms=%.0f max_ms=%.0f"
                              % (_ST["done"], _ST["skipped"], _ST["fallback"], _ST["err"],
                                 _ST["sum_ms"] / max(1, _ST["done"]), _ST["max_ms"]))
        if report:
            _say(report)


def _start_worker():
    """Called under _LOCK. Returns the started thread or None."""
    try:
        th = threading.Thread(target=_worker, daemon=True, name=THREAD_NAME)
        th.start()
        _ST["thread"] = th
        return th
    except Exception:
        return None


def submit(engine, now, energy):
    """True = the explore was handed to the worker (or skipped by the one-in-flight limiter): tick() must NOT run it.
    False = OFF, or the floor: tick() runs it inline exactly as today. Never raises."""
    try:
        c = cfg()
        _arm_note(c)
        if c is None:
            return False
        t = _clock()
        with _LOCK:
            th = _ST["thread"]
            if _ST["busy_since"]:
                if th is None or not th.is_alive():          # the worker died with a job: clear it, run inline
                    _ST["busy_since"] = 0.0
                    _ST["slot"] = None
                    _ST["fallback"] += 1
                    return False
                if t - _ST["busy_since"] >= c["stuck_s"]:     # an explore is stuck: today's inline path
                    _ST["fallback"] += 1
                    return False
                _ST["skipped"] += 1                           # one in flight: the limiter
                return True
            if th is None or not th.is_alive():
                th = _start_worker()
                if th is None:
                    _ST["fallback"] += 1
                    return False
            _ST["slot"] = (engine, now, energy)
            _ST["busy_since"] = t
            _EVENT.set()
        return True
    except Exception:
        return False


def stats():
    try:
        with _LOCK:
            d = {k: v for k, v in _ST.items() if k not in ("thread", "slot")}
            d["worker_alive"] = bool(_ST["thread"] is not None and _ST["thread"].is_alive())
            return d
    except Exception:
        return {}
